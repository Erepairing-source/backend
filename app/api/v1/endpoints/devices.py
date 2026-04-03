"""
Device endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import io
import traceback
import os
import uuid

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.models.device import Device, DeviceRegistration
from app.models.warranty import Warranty, WarrantyStatus
from datetime import datetime, timezone
try:
    import numpy as np
    import cv2
    OPENCV_AVAILABLE = True
except Exception:
    OPENCV_AVAILABLE = False

router = APIRouter()

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


def _save_upload_file(upload: UploadFile, subdir: str) -> str:
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads", subdir)
    os.makedirs(base_dir, exist_ok=True)
    ext = os.path.splitext(upload.filename or "")[1] or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(base_dir, filename)
    with open(file_path, "wb") as f:
        f.write(upload.file.read())
    return f"/uploads/{subdir}/{filename}"


def _decode_qr_from_bytes(image_bytes: bytes) -> Optional[str]:
    try:
        if not OPENCV_AVAILABLE:
            return None
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return None
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(image)
        return data.strip() if data else None
    except Exception:
        return None


def _parse_qr_payload(payload: str) -> dict:
    """
    Accepts QR payload formats:
    - JSON: {"serial_number": "...", "model_number": "...", "brand": "...", "product_category": "..."}
    - Key-value: "serial=...;model=...;brand=...;category=..."
    """
    result = {"serial_number": None, "model_number": None, "brand": None, "product_category": None}
    try:
        import json
        data = json.loads(payload)
        if isinstance(data, dict):
            result["serial_number"] = data.get("serial_number") or data.get("serial")
            result["model_number"] = data.get("model_number") or data.get("model")
            result["brand"] = data.get("brand")
            result["product_category"] = data.get("product_category") or data.get("category")
            return result
    except Exception:
        pass

    # fallback key-value parsing
    parts = [p.strip() for p in payload.replace("|", ";").split(";") if p.strip()]
    for part in parts:
        if "=" in part:
            key, val = [x.strip() for x in part.split("=", 1)]
            key = key.lower()
            if key in ("serial", "serial_number", "sn"):
                result["serial_number"] = val
            elif key in ("model", "model_number"):
                result["model_number"] = val
            elif key in ("brand",):
                result["brand"] = val
            elif key in ("category", "product_category"):
                result["product_category"] = val
    return result


def _build_warranty_summary(warranty_details: Optional[dict]) -> Optional[str]:
    if not warranty_details:
        return None
    warranty_type = warranty_details.get("warranty_type", "standard").replace("_", " ")
    end_date = warranty_details.get("end_date")
    covered_parts = warranty_details.get("covered_parts") or []
    covered_services = warranty_details.get("covered_services") or []

    parts_text = "standard parts coverage" if not covered_parts else f"parts covered: {', '.join(covered_parts)}"
    services_text = "standard labour coverage" if not covered_services else f"services covered: {', '.join(covered_services)}"
    until_text = f"in warranty till {end_date}" if end_date else "warranty active"
    return f"{until_text}; {warranty_type} warranty; {parts_text}; {services_text}."


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_device(
    device_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a new device for the current user"""
    serial_number = device_data.get("serial_number")
    model_number = device_data.get("model_number")
    product_category = device_data.get("product_category")
    brand = device_data.get("brand")
    purchase_date = device_data.get("purchase_date")
    invoice_number = device_data.get("invoice_number")
    invoice_photo = device_data.get("invoice_photo")
    device_photo = device_data.get("device_photo")
    additional_info = device_data.get("additional_info", {})
    registration_method = device_data.get("registration_method", "manual")
    qr_code = device_data.get("qr_code")
    
    if not serial_number or not model_number or not product_category or not brand:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: serial_number, model_number, product_category, brand"
        )
    
    # Check if device with this serial number already exists
    existing_device = db.query(Device).filter(Device.serial_number == serial_number).first()
    if existing_device:
        if existing_device.customer_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this serial number is already registered to you"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this serial number is already registered to another customer"
            )
    
    # Parse purchase date if provided
    purchase_dt = None
    if purchase_date:
        try:
            purchase_dt = datetime.fromisoformat(purchase_date.replace('Z', '+00:00'))
        except:
            pass
    
    # Create device
    device = Device(
        serial_number=serial_number,
        model_number=model_number,
        product_category=product_category,
        brand=brand,
        customer_id=current_user.id,
        organization_id=current_user.organization_id,
        purchase_date=purchase_dt,
        invoice_number=invoice_number,
        invoice_photo=invoice_photo,
        device_photo=device_photo,
        qr_code=qr_code,
        additional_info=additional_info
    )
    
    db.add(device)
    db.flush()
    
    # Create registration record
    registration = DeviceRegistration(
        device_id=device.id,
        registration_method=registration_method,
        registration_data={
            "registered_by": current_user.id,
            "registered_at": datetime.utcnow().isoformat()
        }
    )
    db.add(registration)
    db.commit()
    db.refresh(device)
    
    return {
        "id": device.id,
        "serial_number": device.serial_number,
        "model_number": device.model_number,
        "product_category": device.product_category,
        "brand": device.brand,
        "message": "Device registered successfully"
    }


@router.post("/qr-decode")
async def decode_qr(
    qr_image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Decode QR code from uploaded image"""
    try:
        image_bytes = await qr_image.read()
        qr_payload = _decode_qr_from_bytes(image_bytes)
        if not qr_payload:
            raise HTTPException(status_code=400, detail="QR code not detected")
        parsed = _parse_qr_payload(qr_payload)
        return {
            "raw_payload": qr_payload,
            "parsed": parsed
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QR decode failed: {str(e)}")


@router.post("/register-with-files", status_code=status.HTTP_201_CREATED)
async def register_device_with_files(
    serial_number: str = Form(...),
    model_number: str = Form(...),
    product_category: str = Form(...),
    brand: str = Form(...),
    purchase_date: Optional[str] = Form(None),
    invoice_number: Optional[str] = Form(None),
    registration_method: str = Form("manual"),
    qr_code: Optional[str] = Form(None),
    additional_info: Optional[str] = Form(None),
    invoice_file: Optional[UploadFile] = File(None),
    device_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register device with uploaded invoice/device photos"""
    # Check if device with this serial number already exists
    existing_device = db.query(Device).filter(Device.serial_number == serial_number).first()
    if existing_device:
        if existing_device.customer_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this serial number is already registered to you"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this serial number is already registered to another customer"
            )

    # Parse purchase date if provided
    purchase_dt = None
    if purchase_date:
        try:
            purchase_dt = datetime.fromisoformat(purchase_date.replace('Z', '+00:00'))
        except Exception:
            purchase_dt = None

    invoice_photo = _save_upload_file(invoice_file, "invoices") if invoice_file else None
    device_photo = _save_upload_file(device_file, "devices") if device_file else None

    device = Device(
        serial_number=serial_number,
        model_number=model_number,
        product_category=product_category,
        brand=brand,
        customer_id=current_user.id,
        organization_id=current_user.organization_id,
        purchase_date=purchase_dt,
        invoice_number=invoice_number,
        invoice_photo=invoice_photo,
        device_photo=device_photo,
        qr_code=qr_code,
        additional_info=additional_info or {}
    )

    db.add(device)
    db.flush()

    registration = DeviceRegistration(
        device_id=device.id,
        registration_method=registration_method,
        registration_data={
            "registered_by": current_user.id,
            "registered_at": datetime.utcnow().isoformat()
        }
    )
    db.add(registration)
    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "serial_number": device.serial_number,
        "model_number": device.model_number,
        "product_category": device.product_category,
        "brand": device.brand,
        "invoice_photo": device.invoice_photo,
        "device_photo": device.device_photo,
        "message": "Device registered successfully"
    }


@router.get("/")
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all devices for the current user"""
    devices = db.query(Device).filter(Device.customer_id == current_user.id).all()
    
    result = []
    for device in devices:
        # Check warranty status from warranties relationship
        warranty_status = None
        active_warranty = db.query(Warranty).filter(
            Warranty.device_id == device.id,
            Warranty.status == WarrantyStatus.ACTIVE,
            Warranty.end_date >= datetime.now(timezone.utc)
        ).first()
        
        if active_warranty:
            warranty_status = "in_warranty"
        else:
            # Check if there's any warranty (expired)
            any_warranty = db.query(Warranty).filter(Warranty.device_id == device.id).first()
            if any_warranty:
                warranty_status = "out_of_warranty"
            else:
                warranty_status = "unknown"
        
        result.append({
            "id": device.id,
            "serial_number": device.serial_number,
            "model_number": device.model_number,
            "product_category": device.product_category,
            "brand": device.brand,
            "purchase_date": device.purchase_date.isoformat() if device.purchase_date else None,
            "invoice_number": device.invoice_number,
            "device_photo": device.device_photo,
            "warranty_status": warranty_status,
            "created_at": device.created_at.isoformat() if device.created_at else None
        })
    
    return result


@router.get("/{device_id}")
async def get_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get device details"""
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.customer_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Check warranty status from warranties relationship
    warranty_status = None
    active_warranty = db.query(Warranty).filter(
        Warranty.device_id == device.id,
        Warranty.status == WarrantyStatus.ACTIVE,
        Warranty.end_date >= datetime.now(timezone.utc)
    ).first()
    
    if active_warranty:
        warranty_status = "in_warranty"
    else:
        # Check if there's any warranty (expired)
        any_warranty = db.query(Warranty).filter(Warranty.device_id == device.id).first()
        if any_warranty:
            warranty_status = "out_of_warranty"
        else:
            warranty_status = "unknown"
    
    warranty_details = None
    if active_warranty:
        warranty_details = {
            "warranty_type": active_warranty.warranty_type,
            "start_date": active_warranty.start_date.isoformat(),
            "end_date": active_warranty.end_date.isoformat(),
            "covered_parts": active_warranty.covered_parts,
            "covered_services": active_warranty.covered_services
        }
    warranty_summary = _build_warranty_summary(warranty_details)

    return {
        "id": device.id,
        "serial_number": device.serial_number,
        "model_number": device.model_number,
        "product_category": device.product_category,
        "brand": device.brand,
        "purchase_date": device.purchase_date.isoformat() if device.purchase_date else None,
        "invoice_number": device.invoice_number,
        "invoice_photo": device.invoice_photo,
        "device_photo": device.device_photo,
        "qr_code": device.qr_code,
        "additional_info": device.additional_info or {},
        "warranty_status": warranty_status,
        "warranty_details": warranty_details,
        "warranty_summary": warranty_summary,
        "created_at": device.created_at.isoformat() if device.created_at else None
    }


@router.post("/bulk-register", status_code=status.HTTP_200_OK)
async def bulk_register_devices(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk register devices from Excel file"""
    if not OPENPYXL_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel processing library (openpyxl) is not installed. Please install it with: pip install openpyxl"
        )
    
    # Validate file type
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read file content
        contents = await file.read()
        
        # Load workbook
        workbook = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        worksheet = workbook.active
        
        # Get headers (first row)
        headers = []
        for cell in worksheet[1]:
            headers.append(cell.value.lower().strip() if cell.value else '')
        
        # Find column indices
        serial_col = None
        model_col = None
        category_col = None
        brand_col = None
        purchase_date_col = None
        invoice_col = None
        
        for idx, header in enumerate(headers):
            if 'serial' in header:
                serial_col = idx + 1
            elif 'model' in header:
                model_col = idx + 1
            elif 'category' in header or 'product_category' in header:
                category_col = idx + 1
            elif 'brand' in header:
                brand_col = idx + 1
            elif 'purchase' in header and 'date' in header:
                purchase_date_col = idx + 1
            elif 'invoice' in header:
                invoice_col = idx + 1
        
        if not all([serial_col, model_col, category_col, brand_col]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Excel file must contain columns: serial_number, model_number, product_category, brand"
            )
        
        # Process rows
        successful = 0
        failed = 0
        errors = []
        
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, values_only=False), start=2):
            # Skip empty rows
            if not any(cell.value for cell in row):
                continue
            
            try:
                # Extract values
                serial_number = str(row[serial_col - 1].value).strip() if row[serial_col - 1].value else None
                model_number = str(row[model_col - 1].value).strip() if row[model_col - 1].value else None
                product_category = str(row[category_col - 1].value).strip() if row[category_col - 1].value else None
                brand = str(row[brand_col - 1].value).strip() if row[brand_col - 1].value else None
                
                purchase_date = None
                if purchase_date_col and row[purchase_date_col - 1].value:
                    purchase_val = row[purchase_date_col - 1].value
                    if isinstance(purchase_val, datetime):
                        purchase_date = purchase_val
                    else:
                        try:
                            purchase_date = datetime.fromisoformat(str(purchase_val))
                        except:
                            pass
                
                invoice_number = None
                if invoice_col and row[invoice_col - 1].value:
                    invoice_number = str(row[invoice_col - 1].value).strip()
                
                # Validate required fields
                if not serial_number or not model_number or not product_category or not brand:
                    errors.append(f"Row {row_idx}: Missing required fields")
                    failed += 1
                    continue
                
                # Check if device already exists
                existing_device = db.query(Device).filter(Device.serial_number == serial_number).first()
                if existing_device:
                    if existing_device.customer_id == current_user.id:
                        errors.append(f"Row {row_idx}: Device with serial {serial_number} already registered to you")
                        failed += 1
                        continue
                    else:
                        errors.append(f"Row {row_idx}: Device with serial {serial_number} already registered to another customer")
                        failed += 1
                        continue
                
                # Parse purchase date
                purchase_dt = None
                if purchase_date:
                    if purchase_date.tzinfo is None:
                        purchase_dt = purchase_date.replace(tzinfo=timezone.utc)
                    else:
                        purchase_dt = purchase_date
                
                # Create device
                device = Device(
                    serial_number=serial_number,
                    model_number=model_number,
                    product_category=product_category,
                    brand=brand,
                    customer_id=current_user.id,
                    organization_id=current_user.organization_id,
                    purchase_date=purchase_dt,
                    invoice_number=invoice_number,
                    additional_info={}
                )
                
                db.add(device)
                db.flush()
                
                # Create registration record
                registration = DeviceRegistration(
                    device_id=device.id,
                    registration_method="bulk_excel",
                    registration_data={
                        "registered_by": current_user.id,
                        "registered_at": datetime.utcnow().isoformat(),
                        "file_name": file.filename,
                        "row_number": row_idx
                    }
                )
                db.add(registration)
                
                successful += 1
                
            except Exception as e:
                errors.append(f"Row {row_idx}: {str(e)}")
                failed += 1
                continue
        
        # Commit all successful registrations
        if successful > 0:
            db.commit()
        
        return {
            "total": successful + failed,
            "successful": successful,
            "failed": failed,
            "errors": errors[:50] if len(errors) > 50 else errors,  # Limit errors to 50
            "message": f"Successfully registered {successful} device(s)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error processing bulk registration: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Excel file: {str(e)}"
        )
