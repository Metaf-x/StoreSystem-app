from decimal import Decimal
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app import auth
from app.crud import get_order_by_id
from app.database import SessionLocal

router = APIRouter()
security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_authorized_order(order_id: UUID, db: Session, token: str):
    user_data = auth.verify_token_in_other_service(token)
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    user_id = UUID(user_data["user_id"])
    if order.user_id == user_id:
        return order

    operator_data = auth.verify_token_in_other_service(token, minimum_role="operator")
    if operator_data["role"] not in {"operator", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this order",
        )
    return order


def build_order_pdf(order, title: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Order ID: {order.order_id}", styles["Normal"]),
        Paragraph(f"User ID: {order.user_id}", styles["Normal"]),
        Paragraph(f"Status: {order.status.value}", styles["Normal"]),
        Paragraph(f"Created at: {order.created_at}", styles["Normal"]),
        Spacer(1, 12),
    ]

    rows = [["Product ID", "Warehouse ID", "Quantity", "Price", "Total"]]
    total = Decimal("0")
    for item in order.order_items:
        price = Decimal(str(item.price_at_order))
        line_total = price * item.quantity
        total += line_total
        rows.append([
            str(item.product_id),
            str(item.warehouse_id),
            str(item.quantity),
            f"{price:.2f}",
            f"{line_total:.2f}",
        ])
    rows.append(["", "", "", "Grand total", f"{total:.2f}"])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer


def pdf_response(order, document_kind: str, title: str):
    pdf = build_order_pdf(order, title)
    filename = f"{document_kind}-{order.order_id}.pdf"
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/orders/{order_id}/documents/invoice.pdf", tags=["Order Documents"])
def download_invoice(
    order_id: UUID,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    order = get_authorized_order(order_id, db, credentials.credentials)
    return pdf_response(order, "invoice", "Invoice")


@router.get("/orders/{order_id}/documents/shipment.pdf", tags=["Order Documents"])
def download_shipment(
    order_id: UUID,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    order = get_authorized_order(order_id, db, credentials.credentials)
    return pdf_response(order, "shipment", "Shipment Document")
