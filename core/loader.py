"""อ่านไฟล์ Excel ที่ export จาก TikTok Shop และไฟล์คำนวณต้นทุนของบริษัท

รองรับโครงสร้างไฟล์จริงของ บริษัท มาตัง คอสเมติก จำกัด ทั้งหมด:
1. ชีต SKU: รหัส, ชื่อ, ราคาทุน, ราคาปลีก, ราคาโปร, ราคาตั้งขาย (และ หมวดหมู่ ถ้ามี)
2. ชีต รายละเอียดคำสั่งซื้อ (TikTok Settlement 70 คอลัมน์):
   - กู้คืนชื่อคอลัมน์ F ('ยอดการชำระเงินทั้งหมด') อัตโนมัติ แม้ถูกทับด้วยสูตร =SUM(F2:...)
   - รองรับคอลัมน์รายได้ ค่าธรรมเนียมทั้ง 25 รายการหลัก + รายการย่อย การปรับยอด และข้อมูลสนับสนุนครบทุกคอลัมน์
3. ชีต Order (Order8, Order7, Order9, OrderSKUList ฯลฯ รวมหลายชีตในไฟล์เดียวได้):
   - ตัดแถวคำอธิบายภาษาอังกฤษแถวที่ 2 อัตโนมัติ
   - กู้คืนคอลัมน์ 'ราคาต่อหน่วย' และ 'มูลค่า' ที่แทรกอยู่ระหว่าง 'Product Name' กับ 'Variation' แม้ไม่ได้ตั้งชื่อหัวคอลัมน์
4. ชีต บันทึกการถอน (ประเภทธุรกรรม, ID อ้างอิง, เวลาส่งคำขอ, จำนวน, สถานะ, เวลาที่สำเร็จ, บัญชีธนาคาร)
5. ชีต ads / แคมเปญ (ถ้ามีแยกต่างหากนอกเหนือจากการหักค่าโฆษณาด้วย GMV ในรายละเอียดคำสั่งซื้อ)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import BinaryIO

import pandas as pd

# คอลัมน์หลักที่ใช้ตรวจจับประเภทชีต
SETTLEMENT_KEY = "หมายเลขคำสั่งซื้อ/การปรับ"
ORDER_KEY = "Order ID"
ADS_KEY = "ชื่อแคมเปญ"
SKU_KEY = "ราคาทุน"

# 1. กลุ่มคอลัมน์รายได้ในชีตรายละเอียดคำสั่งซื้อ
SETTLEMENT_REVENUE_COLS = [
    "ยอดการชำระเงินทั้งหมด",
    "จำนวนเงินที่ชำระทั้งหมด",
    "รายได้ทั้งหมด",
    "รายได้รวม",
    "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย",
    "ยอดรวมค่าสินค้าก่อนหักส่วนลด",
    "ส่วนลดจากร้านค้า",
    "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย",
    "ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า",
    "เงินคืนจากส่วนลดร้านค้า",
]

# 2. คอลัมน์ค่าธรรมเนียมระดับหลัก (Level 3) ทั้ง 25 รายการ ที่ผลรวมเท่ากับ 'ค่าธรรมเนียมทั้งหมด'
SETTLEMENT_FEE_TOP_COLS = [
    "ค่าธรรมเนียมคำสั่งซื้อ",
    "ค่าคอมมิชชั่น TikTok Shop",
    "การผ่อนชำระด้วยบัตรเครดิต - มีอัตราดอกเบี้ย",
    "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง",
    "ค่าคอมมิชชั่นแอฟฟิลิเอต",
    "ค่าคอมมิชชั่นของพาร์ทเนอร์แอฟฟิลิเอต",
    "ค่าคอมมิชชั่นแอฟฟิลิเอตสำหรับโฆษณาร้านค้า",
    "เงินมัดจำค่าคอมมิชชั่นของแอฟฟิลิเอต",
    "การคืนเงินค่าคอมมิชชั่นแอฟฟิลิเอต",
    "ค่าคอมมิชชั่นโฆษณาร้านค้าพาร์ทเนอร์แอฟฟิลิเอต",
    "ค่าธรรมเนียมการบริการ SFP",
    "ค่าธรรมเนียมบริการคืนเงินโบนัส",
    "ค่าบริการของคูปองไลฟ์คุ้ม",
    "ค่าบริการคูปอง Xtra",
    "ค่าบริการโปรแกรม EAMS",
    "ค่าบริการแบรนด์ดัง ลดแรง/แฟลชเซล",
    "ค่าธรรมเนียมโปรแกรม TikTok PayLater",
    "ค่าธรรมเนียมสนับสนุนการเติบโตของร้านค้า",
    "ค่าธรรมเนียมโครงสร้างพื้นฐาน",
    "ค่าทรัพยากรแคมเปญ",
    "ค่าธรรมเนียมพรีออเดอร์",
    "คูปอง GMV Max",
    "ภาษีการขายสำหรับคูปอง GMV Max",
    "ค่าโฆษณา GMV Max",
    "Guarantee program fee",
]

# 3. คอลัมน์รายละเอียดย่อยของค่าจัดส่งและภาษีแอฟฟิลิเอต (Level 4 — แสดงประกอบ ไม่บวกซ้ำกับตัวแม่)
SETTLEMENT_SHIPPING_SUB_COLS = [
    "ค่าธรรมเนียมการจัดส่งจริง",
    "ส่วนลดค่าธรรมเนียมการจัดส่งจากแพลตฟอร์ม",
    "ค่าธรรมเนียมการจัดส่งของลูกค้า",
    "ค่าธรรมเนียมการจัดส่งสินค้าคืนตามจริง",
    "เงินคืนสำหรับค่าจัดส่ง",
    "เงินสนับสนุนการจัดส่ง",
    "ค่าจัดส่งสินค้าที่แลกเปลี่ยน (ลูกค้าเป็นผู้จ่าย)",
    "ค่าจัดส่งสินค้าทดแทน (ลูกค้าเป็นผู้จ่าย)",
    "Guarantee program reimbursement",
]

SETTLEMENT_AFFILIATE_SUB_COLS = [
    "ค่าคอมมิชชั่นไม่ใช่แอฟฟิลิเอตก่อนหักภาษีเงินได้บุคคลธรรมดา",
    "ภาษีเงินได้บุคคลธรรมดาที่หักไว้จากคอมมิชชั่นของแอฟฟิลิเอต",
    "ค่าคอมมิชชั่นโฆษณาร้านค้าแอฟฟิลิเอตก่อน PIT",
    "ภาษีเงินได้บุคคลธรรมดาหัก ณ ที่จ่ายจากค่าคอมมิชชั่นโฆษณาร้านค้าแอฟฟิลิเอต",
]

# 4. คอลัมน์การปรับยอดและข้อมูลสนับสนุนเพิ่มเติมในชีตรายละเอียดคำสั่งซื้อ
SETTLEMENT_EXTRA_NUMERIC_COLS = [
    "จำนวนการปรับยอด",
    "การชำระเงินของลูกค้า",
    "การคืนเงินจากลูกค้า",
    "คูปองส่วนลดร่วมของผู้ขาย",
    "การคืนเงินคูปองส่วนลดร่วมของผู้ขาย",
    "ส่วนลดจากแพลตฟอร์ม",
    "การคืนเงินส่วนลดจากแพลตฟอร์ม",
    "คูปองส่วนลดร่วมของแพลตฟอร์ม",
    "การคืนเงินคูปองส่วนลดร่วมของแพลตฟอร์ม",
    "ส่วนลดค่าจัดส่งจากร้านค้า",
    "น้ำหนักพัสดุโดยประมาณ",
    "น้ำหนักที่เรียกเก็บเงิน",
]

SETTLEMENT_NUMERIC = (
    SETTLEMENT_REVENUE_COLS
    + ["ค่าธรรมเนียมทั้งหมด"]
    + SETTLEMENT_FEE_TOP_COLS
    + SETTLEMENT_SHIPPING_SUB_COLS
    + SETTLEMENT_AFFILIATE_SUB_COLS
    + SETTLEMENT_EXTRA_NUMERIC_COLS
)

# คอลัมน์ตัวเลขในชีต Order (ตรงตามโครงสร้าง TikTok Order Export + ราคาต่อหน่วย/มูลค่า ของบริษัท)
ORDER_NUMERIC = [
    "ราคาต่อหน่วย",
    "มูลค่า",
    "Quantity",
    "Sku Quantity of return",
    "SKU Unit Original Price",
    "SKU Subtotal Before Discount",
    "SKU Platform Discount",
    "SKU Seller Discount",
    "SKU Subtotal After Discount",
    "Shipping Fee After Discount",
    "Original Shipping Fee",
    "Shipping Fee Seller Discount",
    "Shipping Fee Platform Discount",
    "Payment platform discount",
    "Taxes",
    "Order Amount",
    "Order Refund Amount",
    "Weight(kg)",
]

ADS_NUMERIC = ["ค่าใช้จ่ายที่เป็นเงินสด", "ค่าใช้จ่ายเครดิต", "ค่าใช้จ่ายเครดิตโฆษณา", "จำนวนรวม"]
SKU_NUMERIC = ["ราคาทุน", "ราคาปลีก", "ราคาโปร", "ราคาตั้งขาย"]

# รองรับไฟล์ Settlement ของ TikTok ที่ถูกส่งออกเป็นหัวตารางภาษาอังกฤษ (เช่น ชีต 'ขายเดือน2บังตี๋' ใน ต้นทุน2569-02.xlsx)
EN_SETTLEMENT_HEADER_MAP: dict[str, str] = {
    "Order/adjustment ID": SETTLEMENT_KEY,
    "Type": "ประเภทธุรกรรม",
    "Order created time": "เวลาที่สร้างคำสั่งซื้อ",
    "Order settled time": "เวลาที่ชำระคำสั่งซื้อ",
    "Currency": "สกุลเงิน",
    "Total settlement amount": "ยอดการชำระเงินทั้งหมด",
    "Total revenue": "รายได้ทั้งหมด",
    "Subtotal after seller discounts": "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย",
    "Subtotal before discounts": "ยอดรวมค่าสินค้าก่อนหักส่วนลด",
    "Seller discounts": "ส่วนลดจากร้านค้า",
    "Refund subtotal after seller discounts": "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย",
    "Refund subtotal before seller discounts": "ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า",
    "Refund of seller discounts": "เงินคืนจากส่วนลดร้านค้า",
    "Total Fees": "ค่าธรรมเนียมทั้งหมด",
    "Total fees": "ค่าธรรมเนียมทั้งหมด",
    "Transaction fee": "ค่าธรรมเนียมคำสั่งซื้อ",
    "TikTok Shop commission fee": "ค่าคอมมิชชั่น TikTok Shop",
    "Seller shipping fee": "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง",
    "Affiliate commission": "ค่าคอมมิชชั่นแอฟฟิลิเอต",
    "Affiliate partner commission": "ค่าคอมมิชชั่นของพาร์ทเนอร์แอฟฟิลิเอต",
    "Affiliate shop ads commission": "ค่าคอมมิชชั่นแอฟฟิลิเอตสำหรับโฆษณาร้านค้า",
    "SFP service fee": "ค่าธรรมเนียมการบริการ SFP",
    "LIVE Specials service fee": "ค่าบริการของคูปองไลฟ์คุ้ม",
    "Voucher Xtra service fee": "ค่าบริการคูปอง Xtra",
    "Adjustment amount": "จำนวนการปรับยอด",
    "Customer payment": "การชำระเงินของลูกค้า",
    "Customer refund": "การคืนเงินจากลูกค้า",
    "Platform discounts": "ส่วนลดจากแพลตฟอร์ม",
    "Refund of platform discounts": "การคืนเงินส่วนลดจากแพลตฟอร์ม",
}

EN_TXN_TYPE_MAP: dict[str, str] = {
    "Order": "คำสั่งซื้อ",
    "GMV Payment for TikTok Ads": "การชำระเงินด้วย GMV สำหรับโฆษณา TikTok",
    "GMV Payment for Promote": "การชำระเงินด้วย GMV สำหรับการโปรโมท",
    "Logistics reimbursement": "เงินชดเชยด้านโลจิสติกส์",
    "Platform reimbursement": "การชดเชยจากแพลตฟอร์ม",
    "Deductions incurred by seller": "การหักเงินที่เกิดจากผู้ขาย",
}

# คำอธิบายค่าธรรมเนียมและการปรับยอดมาตรฐานตามชีต 'คำอธิบายค่าธรรมเนียม' ของ TikTok Shop
FEE_DESCRIPTIONS: dict[str, str] = {
    "ยอดการชำระเงินทั้งหมด": "ยอดเงินรวมหลังจากคำนวณยอดขายสุทธิ (รายได้ทั้งหมด) ค่าธรรมเนียมทั้งหมด และการปรับยอด",
    "รายได้ทั้งหมด": "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย + ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย",
    "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย": "ราคาสินค้าหลังจากหักส่วนลดจากผู้ขาย (ยอดรวมก่อนหักส่วนลด + ส่วนลดจากร้านค้า)",
    "ยอดรวมค่าสินค้าก่อนหักส่วนลด": "ราคารวมก่อนหักส่วนลดจากผู้ขายและ TikTok Shop",
    "ส่วนลดจากร้านค้า": "โปรโมชั่นที่สนับสนุนโดยผู้ขาย เช่น คูปองหรือส่วนลดสินค้า",
    "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย": "ยอดรวมเงินคืนจากสินค้า SKU ที่ลูกค้าคืน หลังจากหักส่วนลดจากร้านค้าทั้งหมด",
    "ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า": "ยอดรวมเงินคืนจากสินค้าที่ลูกค้าคืน ก่อนหักส่วนลดจากร้านค้า",
    "เงินคืนจากส่วนลดร้านค้า": "เงินคืนจากส่วนลดที่ร้านค้าให้กับลูกค้า ก่อนมีการคืนสินค้า",
    "ค่าธรรมเนียมทั้งหมด": "ผลรวมค่าธรรมเนียมทั้งหมดที่แพลตฟอร์มเรียกเก็บจากคำสั่งซื้อ",
    "ค่าธรรมเนียมคำสั่งซื้อ": "(ยอดชำระเงินของลูกค้า - ยอดเงินคืน) × อัตรา % ที่กำหนด",
    "ค่าคอมมิชชั่น TikTok Shop": "คำนวณตามราคาของสินค้าหลังหักส่วนลดของผู้ขาย คูณด้วยอัตราหมวดหมู่พื้นฐาน",
    "การผ่อนชำระด้วยบัตรเครดิต - มีอัตราดอกเบี้ย": "ค่าบริการบัตรเครดิตผ่อนชำระ (IPP) สำหรับคำสั่งซื้อที่สำเร็จ",
    "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง": "ค่าจัดส่งตามจริง - ส่วนลดค่าจัดส่งจาก TikTok Shop - ค่าจัดส่งที่ลูกค้าจ่าย",
    "ค่าคอมมิชชั่นแอฟฟิลิเอต": "(ราคาสินค้าไม่รวมภาษี - ส่วนลดผู้ขาย) × อัตราค่าคอมมิชชั่นครีเอเตอร์",
    "ค่าคอมมิชชั่นของพาร์ทเนอร์แอฟฟิลิเอต": "(ราคาสินค้าไม่รวมภาษี - ส่วนลดผู้ขาย) × อัตราค่าคอมมิชชั่นพาร์ทเนอร์",
    "ค่าคอมมิชชั่นแอฟฟิลิเอตสำหรับโฆษณาร้านค้า": "(ราคาสินค้าไม่รวมภาษี - ส่วนลดผู้ขาย) × อัตราค่าคอมมิชชั่นโฆษณาร้านค้า",
    "ค่าคอมมิชชั่นโฆษณาร้านค้าพาร์ทเนอร์แอฟฟิลิเอต": "ค่าคอมมิชชั่นโฆษณาที่ผู้ขายจ่ายให้พาร์ทเนอร์แอฟฟิลิเอต (TAP)",
    "ค่าธรรมเนียมการบริการ SFP": "ค่าธรรมเนียมการเข้าร่วมโปรแกรมส่งฟรี (Shipping Fee Program)",
    "ค่าธรรมเนียมบริการคืนเงินโบนัส": "ค่าธรรมเนียมการเข้าร่วมโปรแกรมคืนเงินโบนัส",
    "ค่าบริการของคูปองไลฟ์คุ้ม": "ค่าบริการการเข้าร่วมโปรแกรมคูปองไลฟ์คุ้ม",
    "ค่าบริการคูปอง Xtra": "ค่าบริการการเข้าร่วมโปรแกรมคูปอง Xtra",
    "ค่าบริการโปรแกรม EAMS": "ค่าธรรมเนียมบริการโปรแกรมโซลูชั่นการตลาดแอฟฟิลิเอตภายนอก",
    "ค่าบริการแบรนด์ดัง ลดแรง/แฟลชเซล": "ค่าธรรมเนียมแคมเปญแบรนด์ดัง ลดแรง / แฟลชเซล",
    "ค่าธรรมเนียมโปรแกรม TikTok PayLater": "ค่าธรรมเนียมการเข้าร่วมโปรแกรม TikTok PayLater",
    "ค่าธรรมเนียมสนับสนุนการเติบโตของร้านค้า": "เรียกเก็บกับพัสดุที่จัดส่งแล้ว คำนวณจากราคาขายลบส่วนลดผู้ขาย (สูงสุด 199 บาท/ชิ้น)",
    "ค่าธรรมเนียมโครงสร้างพื้นฐาน": "ค่าบริการดูแลรักษาและพัฒนาโครงสร้างพื้นฐานทางเทคนิคของแพลตฟอร์ม",
    "ค่าทรัพยากรแคมเปญ": "ยอดค่าทรัพยากรแคมเปญจากโปรแกรมที่ผู้ขายเข้าร่วม",
    "ค่าธรรมเนียมพรีออเดอร์": "ค่าบริการจากการขายสินค้าพรีออเดอร์",
    "คูปอง GMV Max": "ค่าใช้จ่ายของคูปอง GMV Max",
    "ภาษีการขายสำหรับคูปอง GMV Max": "ภาษีการขายที่มีผลกับค่าใช้จ่ายของคูปอง GMV Max",
    "ค่าโฆษณา GMV Max": "(ยอดชำระเงินทั้งหมด + ส่วนลดจากแพลตฟอร์มสำหรับสินค้า) ÷ ROI โฆษณา × (1 + อัตราภาษี)",
    "Guarantee program fee": "ค่าเบี้ยประกันต่อคำสั่งซื้อสำหรับความคุ้มครองประกันภัย",
    "จำนวนการปรับยอด": "ยอดรวมรายการปรับยอด/ชดเชย/หักชำระค่าโฆษณาด้วย GMV",
    "การชำระเงินด้วย GMV สำหรับโฆษณา TikTok": "เมื่อเปิดใช้งาน 'ชำระเงินค่าโฆษณาด้วย GMV' รายได้ของร้านค้าจะถูกหักไปจ่ายเป็นค่าโฆษณา TikTok",
    "การชำระเงินด้วย GMV สำหรับการโปรโมท": "จำนวนเงินรายได้ของร้านค้าที่ถูกนำไปจ่ายค่าการโปรโมท",
    "เงินชดเชยด้านโลจิสติกส์": "เงินชดเชยที่จ่ายโดย TikTok Shop สำหรับความเสียหายจากปัญหาด้านโลจิสติกส์",
    "การชดเชยจากแพลตฟอร์ม": "ค่าชดเชยให้กับผู้ขายจากการอุทธรณ์ข้อโต้แย้งของลูกค้าสำเร็จ",
    "ค่าชดเชยจากแพลตฟอร์ม": "ค่าชดเชยให้กับผู้ขายจากการอุทธรณ์ข้อโต้แย้งของลูกค้าสำเร็จ",
    "การชำระเงินของลูกค้า": "ยอดรวมหลังส่วนลดผู้ขาย - ส่วนลดแพลตฟอร์ม + ค่าจัดส่งของลูกค้า",
    "การคืนเงินจากลูกค้า": "จำนวนเงินที่คืนให้กับลูกค้า",
    "ส่วนลดจากแพลตฟอร์ม": "ส่วนลดทั้งหมดที่สนับสนุนโดยแพลตฟอร์ม TikTok Shop (คูปอง/แฟลชดีล/ส่วนลดร่วม)",
}


@dataclass
class LoadedWorkbook:
    """ผลลัพธ์การอ่านไฟล์ Excel 1 ไฟล์"""

    name: str
    settlement: pd.DataFrame = field(default_factory=pd.DataFrame)
    orders: pd.DataFrame = field(default_factory=pd.DataFrame)
    ads: pd.DataFrame = field(default_factory=pd.DataFrame)
    sku: pd.DataFrame = field(default_factory=pd.DataFrame)
    withdrawals: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_settlement: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_orders: pd.DataFrame = field(default_factory=pd.DataFrame)
    extra_sheets: dict[str, pd.DataFrame] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _find_header_row(raw: pd.DataFrame, keys: tuple[str, ...], max_scan: int = 10) -> int | None:
    """หาแถวที่มีชื่อคอลัมน์ครบทุกตัวใน keys"""
    for i in range(min(max_scan, len(raw))):
        values = {str(v).strip() for v in raw.iloc[i].tolist() if pd.notna(v)}
        if all(k in values for k in keys):
            return i
    return None


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def _recover_company_headers(header: list[str], kind: str, second_row: list[str] | None = None) -> list[str]:
    """กู้คืนชื่อคอลัมน์ที่ฝ่ายบัญชีใส่สูตรทับหัวตาราง หรือแทรกคอลัมน์โดยไม่ใส่ชื่อหัวตาราง"""
    hdr = [EN_SETTLEMENT_HEADER_MAP.get(h, h) if kind == "settlement" else h for h in header]
    if kind == "settlement":
        # ในไฟล์จริง คอลัมน์ F (ถัดจาก 'สกุลเงิน') คือ 'ยอดการชำระเงินทั้งหมด'
        # แต่มักถูกเขียนสูตร =SUM(F2:...) ทับหัวคอลัมน์ ทำให้ชื่อกลายเป็นตัวเลขหรือค่าว่าง
        has_total_settle = any(c in hdr for c in ("ยอดการชำระเงินทั้งหมด", "จำนวนเงินที่ชำระทั้งหมด"))
        if not has_total_settle and "สกุลเงิน" in hdr:
            curr_idx = hdr.index("สกุลเงิน")
            rev_indices = [hdr.index(c) for c in ("รายได้ทั้งหมด", "รายได้รวม") if c in hdr]
            rev_idx = min(rev_indices) if rev_indices else len(hdr)
            if curr_idx + 1 < rev_idx:
                cand = hdr[curr_idx + 1]
                if not cand or cand.lower() == "nan" or _is_number(cand) or cand.startswith("="):
                    hdr[curr_idx + 1] = "ยอดการชำระเงินทั้งหมด"

    elif kind == "orders":
        # ในชีต Order บางเดือนแทรกคอลัมน์ระหว่าง 'Product Name' กับ 'Variation' เพื่อเก็บราคาทุนต่อหน่วย
        # (เช่น ไม่พิมพ์หัวตาราง, พิมพ์ไว้ในแถวที่ 2 ว่า 'ราคาทุน', หรือพิมพ์ว่า 'ต้นทุน')
        if "ราคาต่อหน่วย" not in hdr and "Product Name" in hdr and "Variation" in hdr:
            p_idx = hdr.index("Product Name")
            v_idx = hdr.index("Variation")
            if v_idx > p_idx + 1:
                mid = list(range(p_idx + 1, v_idx))
                cost_aliases = {"ราคาต่อหน่วย", "ราคาทุน", "ต้นทุน"}
                matched = False
                for i in mid:
                    if hdr[i] in cost_aliases:
                        hdr[i] = "ราคาต่อหน่วย"
                        matched = True
                        break
                if not matched and second_row:
                    for i in mid:
                        if i < len(second_row) and second_row[i] in cost_aliases and (not hdr[i] or hdr[i].lower() == "nan"):
                            hdr[i] = "ราคาต่อหน่วย"
                            matched = True
                            break
                if not matched and (not hdr[p_idx + 1] or hdr[p_idx + 1].lower() == "nan"):
                    hdr[p_idx + 1] = "ราคาต่อหน่วย"
                if v_idx - p_idx == 3 and "มูลค่า" not in hdr and (not hdr[p_idx + 2] or hdr[p_idx + 2].lower() == "nan"):
                    hdr[p_idx + 2] = "มูลค่า"
    return hdr


def _frame_from_raw(raw: pd.DataFrame, header_row: int, kind: str = "") -> pd.DataFrame:
    header = [str(h).strip() if pd.notna(h) else "" for h in raw.iloc[header_row].tolist()]
    second_row = (
        [str(h).strip() if pd.notna(h) else "" for h in raw.iloc[header_row + 1].tolist()]
        if header_row + 1 < len(raw)
        else None
    )
    header = _recover_company_headers(header, kind, second_row=second_row)
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = header
    # ตัดคอลัมน์ว่างหรือคอลัมน์ผลรวมสูตรชั่วคราว (เช่น คอลัมน์ G, H ที่ใส่ =SUM(...) ไว้ เพราะระบบคำนวณใหม่ให้อัตโนมัติ)
    # สำหรับชีต settlement ตัดคอลัมน์ 'ต้นทุน' / 'กำไร' ที่ฝ่ายบัญชีพิมพ์เองด้วย เพื่อคำนวณใหม่จากตาราง SKU เสมอ
    drop_custom = {"ต้นทุน", "กำไร"} if kind == "settlement" else set()
    keep = [
        c
        for c in df.columns
        if c and c.lower() != "nan" and not _is_number(c) and not c.startswith("=") and c not in drop_custom
    ]
    df = df.loc[:, keep]
    df = df.loc[:, ~df.columns.duplicated()]
    return df.dropna(how="all").reset_index(drop=True)


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def _clean_settlement(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df[SETTLEMENT_KEY].notna()].copy()
    df[SETTLEMENT_KEY] = df[SETTLEMENT_KEY].astype(str).str.strip()
    df = df[(df[SETTLEMENT_KEY] != "") & (df[SETTLEMENT_KEY].str.lower() != "nan")]
    if "ประเภทธุรกรรม" in df.columns:
        df["ประเภทธุรกรรม"] = df["ประเภทธุรกรรม"].fillna("คำสั่งซื้อ").astype(str).str.strip().replace(EN_TXN_TYPE_MAP)
    df = _to_numeric(df, SETTLEMENT_NUMERIC)

    has_gross_ref = ("ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย" in df.columns) or ("ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย" in df.columns)
    gross_col = df["ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย"] if "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย" in df.columns else pd.Series(0.0, index=df.index)
    ref_col = df["ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย"] if "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย" in df.columns else pd.Series(0.0, index=df.index)
    calc_rev = gross_col + ref_col

    # แก้กรณีไฟล์บางเดือน (เช่น 2569-07-1) มีคอลัมน์ 'รายได้ทั้งหมด' ว่าง (0.00) ต่อท้าย แต่ยอดขายจริงอยู่ใน 'รายได้รวม' / ยอดรวมค่าสินค้า+เงินคืน
    if "รายได้ทั้งหมด" not in df.columns or (df["รายได้ทั้งหมด"].abs().sum() < 1e-9 and calc_rev.abs().sum() > 1e-9):
        if has_gross_ref and calc_rev.abs().sum() > 1e-9:
            df["รายได้ทั้งหมด"] = calc_rev
        elif "รายได้รวม" in df.columns:
            df["รายได้ทั้งหมด"] = df["รายได้รวม"]

    if "ยอดการชำระเงินทั้งหมด" not in df.columns:
        if "จำนวนเงินที่ชำระทั้งหมด" in df.columns:
            df["ยอดการชำระเงินทั้งหมด"] = df["จำนวนเงินที่ชำระทั้งหมด"]
        elif "รายได้รวม" in df.columns:
            fee_c = df["ค่าธรรมเนียมทั้งหมด"] if "ค่าธรรมเนียมทั้งหมด" in df.columns else 0.0
            adj_c = df["จำนวนการปรับยอด"] if "จำนวนการปรับยอด" in df.columns else 0.0
            expected_settle = df.get("รายได้ทั้งหมด", 0.0) + fee_c + adj_c
            # ในไฟล์ TikTok เดือนเก่า (พ.ค.-ส.ค.) คอลัมน์ F ชื่อ 'รายได้รวม' คือยอดโอนสุทธิ (Total settlement amount)
            if (df["รายได้รวม"] - expected_settle).abs().max() < 1.0:
                df["ยอดการชำระเงินทั้งหมด"] = df["รายได้รวม"]

    if "รายได้รวม" not in df.columns and "รายได้ทั้งหมด" in df.columns:
        df["รายได้รวม"] = df["รายได้ทั้งหมด"]

    for c in SETTLEMENT_NUMERIC:
        if c not in df.columns:
            df[c] = 0.0

    for c in ("เวลาที่สร้างคำสั่งซื้อ", "เวลาที่ชำระคำสั่งซื้อ"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")
    return df.reset_index(drop=True)


def _clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df[ORDER_KEY].notna()].copy()
    df[ORDER_KEY] = df[ORDER_KEY].astype(str).str.strip()
    # ตัดแถวคำอธิบายคอลัมน์ภาษาอังกฤษแถวที่ 2 ของ TikTok (เช่น "Platform unique order ID.")
    df = df[df[ORDER_KEY].str.fullmatch(r"\d+")]

    # เก็บค่าตัวเลขดิบของ ราคาต่อหน่วย ก่อน fillna(0) เพื่อให้แยกแยะค่าว่าง/#N/A กับตัวเลขจริงได้
    for c in ORDER_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if "Seller SKU" in df.columns:
        df["Seller SKU"] = df["Seller SKU"].astype(str).str.strip()

    for t_col in ("Created Time", "Paid Time", "Delivered Time", "Cancelled Time"):
        if t_col in df.columns:
            df[t_col] = pd.to_datetime(df[t_col], errors="coerce", format="mixed", dayfirst=True)
    return df.reset_index(drop=True)


def orders_from_raw(raw: pd.DataFrame, sheet_label: str = "") -> pd.DataFrame:
    """แปลงแถวคำสั่งซื้อดิบ (เช่น จากคลังคำสั่งซื้อสะสม) ให้อยู่ในรูปแบบเดียวกับ LoadedWorkbook.orders"""
    if raw is None or raw.empty or ORDER_KEY not in raw.columns:
        return pd.DataFrame()
    df = _clean_orders(raw.copy())
    if not df.empty:
        df["_order_sheet"] = sheet_label
    return df


def _clean_ads(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df[ADS_KEY].notna()].copy()
    df = _to_numeric(df, ADS_NUMERIC)
    if "วันที่" in df.columns:
        df["วันที่"] = pd.to_datetime(df["วันที่"], errors="coerce", format="mixed")
    return df.reset_index(drop=True)


def _clean_sku(df: pd.DataFrame) -> pd.DataFrame:
    if "รหัส" not in df.columns:
        return df.iloc[0:0]
    df = df[df["รหัส"].notna()].copy()
    raw_code = df["รหัส"].astype(str)
    clean_code = raw_code.str.strip()
    df["_ws_rank"] = (raw_code != clean_code).astype(int)
    df["รหัส"] = clean_code
    df = df[(df["รหัส"] != "") & (df["รหัส"].str.lower() != "nan")]
    df = _to_numeric(df, SKU_NUMERIC)
    # ยึดบรรทัดแรกที่ตรงรหัสเป๊ะก่อนเหมือนสูตร =VLOOKUP(..., FALSE) ของ Excel
    df = df.sort_values("_ws_rank", kind="mergesort").drop_duplicates(subset="รหัส", keep="first").drop(columns=["_ws_rank"])
    return df.reset_index(drop=True)


def _clean_withdrawals(df: pd.DataFrame) -> pd.DataFrame:
    if "ประเภทธุรกรรม" not in df.columns:
        return df.iloc[0:0]
    df = df[df["ประเภทธุรกรรม"].notna()].copy()
    df = _to_numeric(df, ["จำนวน"])
    for c in ("เวลาส่งคำขอ", "เวลาที่สำเร็จ"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")
    return df.reset_index(drop=True)


from pathlib import Path


def get_data_dir() -> Path:
    """ค้นหาโฟลเดอร์ data/ ที่ถูกต้อง ไม่ว่าจะรันจาก root หรือ cost_profit_system"""
    candidates = [
        Path("data"),
        Path("../data"),
        Path(__file__).resolve().parent.parent.parent / "data",
        Path(__file__).resolve().parent.parent / "data",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c.resolve()
    return (Path(__file__).resolve().parent.parent.parent / "data").resolve()


def scan_data_directory(dir_path: str | Path | None = None) -> dict[str, list[dict]]:
    """สแกนหาไฟล์ในโฟลเดอร์ data/ แยกเป็นหมวดหมู่ คำสั่งซื้อ, income, ต้นทุน"""
    p = Path(dir_path) if dir_path else get_data_dir()
    res: dict[str, list[dict]] = {"orders": [], "income": [], "cost": [], "other": []}
    if not p.exists():
        return res

    for f in sorted(p.iterdir()):
        if f.is_file() and f.suffix.lower() in (".xlsx", ".xls") and not f.name.startswith("~$"):
            fname = f.name
            size_mb = f.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 1.0 else f"{f.stat().st_size / 1024:.0f} KB"
            info = {
                "name": fname,
                "path": str(f.resolve()),
                "size_bytes": f.stat().st_size,
                "size_str": size_str,
            }
            lower_name = fname.lower()
            if "คำสั่งซื้อ" in fname or "order" in lower_name:
                res["orders"].append(info)
            elif "income" in lower_name or "รายได้" in fname:
                res["income"].append(info)
            elif "ต้นทุน" in fname or "cost" in lower_name:
                res["cost"].append(info)
            else:
                res["other"].append(info)
    return res


def _parse_sheet_xml_fallback(file_data, target_sheet_name: str) -> pd.DataFrame:
    """อ่านชีตโดยตรงจาก OpenXML กรณีไฟล์คำสั่งซื้อ TikTok export โครงสร้างที่ openpyxl อ่านได้ไม่ครบ (เช่น มีหลาย row r=1)"""
    import zipfile
    import xml.etree.ElementTree as ET
    import re
    from io import BytesIO

    try:
        if hasattr(file_data, "seek"):
            file_data.seek(0)
            z = zipfile.ZipFile(file_data, "r")
        elif isinstance(file_data, (str, Path)):
            z = zipfile.ZipFile(str(file_data), "r")
        else:
            z = zipfile.ZipFile(BytesIO(file_data), "r")

        with z:
            ss = []
            if "xl/sharedStrings.xml" in z.namelist():
                for event, elem in ET.iterparse(z.open("xl/sharedStrings.xml"), events=("end",)):
                    if elem.tag.endswith("si"):
                        ss.append("".join([t.text for t in elem.iter() if t.text and t.tag.endswith("t")]))
                        elem.clear()

            wb_tree = ET.fromstring(z.read("xl/workbook.xml"))
            rel_tree = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            rel_map = {r.attrib["Id"]: r.attrib["Target"].lstrip("/") for r in rel_tree}

            target_path = None
            for s in wb_tree.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
                if s.attrib.get("name") == target_sheet_name:
                    r_id = s.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
                    t = rel_map[r_id]
                    target_path = t if t.startswith("xl/") else "xl/" + t
                    if target_path.startswith("xl/xl/"):
                        target_path = target_path[3:]
                    break

            if not target_path:
                return pd.DataFrame()

            rows = {}
            col_map = {}

            def col_to_idx(col):
                if col not in col_map:
                    idx = 0
                    for ch in col:
                        idx = idx * 26 + (ord(ch) - ord("A") + 1)
                    col_map[col] = idx - 1
                return col_map[col]

            with z.open(target_path) as f:
                for event, elem in ET.iterparse(f, events=("end",)):
                    if elem.tag.endswith("c"):
                        ref = elem.attrib.get("r", "")
                        m = re.match(r"([A-Z]+)(\d+)", ref)
                        if m:
                            col_str, r_str = m.groups()
                            r_num = int(r_str)
                            c_idx = col_to_idx(col_str)
                            t = elem.attrib.get("t", "")
                            v = elem.find("{*}v")
                            val = ""
                            if t == "s" and v is not None and v.text:
                                val = ss[int(v.text)] if int(v.text) < len(ss) else ""
                            elif t == "str":
                                val = "".join([ch.text for ch in elem if ch.text])
                            elif v is not None and v.text:
                                val = v.text
                            if r_num not in rows:
                                rows[r_num] = {}
                            rows[r_num][c_idx] = val
                        elem.clear()

            if not rows:
                return pd.DataFrame()

            max_col = max(max(r.keys()) for r in rows.values()) + 1
            data_matrix = []
            for r_num in sorted(rows.keys()):
                r_dict = rows[r_num]
                data_matrix.append([r_dict.get(c, "") for c in range(max_col)])

            return pd.DataFrame(data_matrix)
    except Exception:
        return pd.DataFrame()


def load_workbook(file: str | BinaryIO, name: str | None = None) -> LoadedWorkbook:
    """อ่านทุกชีตในไฟล์ แล้วจัดประเภทชีตอัตโนมัติจากชื่อคอลัมน์มาตรฐาน (ใช้ Calamine Engine เพื่อความเร็วสูงสุด)"""
    if hasattr(file, "read"):
        data = BytesIO(file.read())
        name = name or getattr(file, "name", "uploaded.xlsx")
    else:
        data = file
        name = name or str(file)

    # เลือกใช้ calamine engine ถ้ามี (เร็วกว่า openpyxl 5-10 เท่า)
    engine = "openpyxl"
    try:
        import python_calamine  # noqa
        engine = "calamine"
    except ImportError:
        pass

    try:
        if isinstance(data, BytesIO):
            data.seek(0)
        xl = pd.ExcelFile(data, engine=engine)
    except Exception:
        if isinstance(data, BytesIO):
            data.seek(0)
        xl = pd.ExcelFile(data, engine="openpyxl")

    # ข้ามเฉพาะชีตสรุปข้อความนิ่งในการคำนวณหลัก แต่เก็บสำเนาไว้ใน extra_sheets สำหรับ export
    skip_sheets = {"รายงาน", "คำอธิบายค่าธรรมเนียม"}
    result = LoadedWorkbook(name=name)

    for s in xl.sheet_names:
        s_clean = str(s).strip()
        if s_clean in skip_sheets:
            try:
                result.extra_sheets[s_clean] = pd.read_excel(xl, sheet_name=s, header=None)
            except Exception:
                pass

    keep_sheets = [s for s in xl.sheet_names if str(s).strip() not in skip_sheets]
    sheets = pd.read_excel(xl, sheet_name=keep_sheets, header=None, dtype=str)
    order_frames: list[pd.DataFrame] = []
    raw_order_frames: list[pd.DataFrame] = []

    for sheet_name, raw in sheets.items():
        if raw.empty or raw.shape[1] <= 1:
            fb_df = _parse_sheet_xml_fallback(data, str(sheet_name))
            if not fb_df.empty:
                raw = fb_df
        if raw.empty:
            continue
        for keys, kind in (
            ((SETTLEMENT_KEY, "ประเภทธุรกรรม"), "settlement"),
            (("Order/adjustment ID", "Type"), "settlement"),
            ((ORDER_KEY, "Seller SKU", "Quantity"), "orders"),
            ((ADS_KEY, "จำนวนรวม"), "ads"),
            (("รหัส", SKU_KEY), "sku"),
            (("ประเภทธุรกรรม", "ID อ้างอิง", "จำนวน"), "withdrawals"),
        ):
            hdr = _find_header_row(raw, keys)
            if hdr is None:
                continue
            df = _frame_from_raw(raw, hdr, kind=kind)
            if kind == "settlement":
                raw_df = df.copy()
                df = _clean_settlement(df)
                if len(df) > len(result.settlement):
                    result.settlement = df
                    result.raw_settlement = raw_df
            elif kind == "orders":
                raw_order_frames.append(df.copy())
                df = _clean_orders(df)
                if not df.empty:
                    df["_order_sheet"] = str(sheet_name)
                    sku_c = "SKU ID" if "SKU ID" in df.columns else "Seller SKU"
                    df["_line_seq"] = df.groupby([ORDER_KEY, sku_c]).cumcount()
                    order_frames.append(df)
            elif kind == "ads":
                df = _clean_ads(df)
                if not df.empty:
                    result.ads = pd.concat([result.ads, df], ignore_index=True)
            elif kind == "sku":
                df = _clean_sku(df)
                if not df.empty:
                    result.sku = df
            elif kind == "withdrawals":
                df = _clean_withdrawals(df)
                if not df.empty:
                    result.withdrawals = pd.concat([result.withdrawals, df], ignore_index=True)
            if not df.empty:
                result.notes.append(f"ชีต '{sheet_name}' → {kind} ({len(df):,} แถว)")
            break

    if order_frames:
        concat_orders = pd.concat(order_frames, ignore_index=True)
        sku_c = "SKU ID" if "SKU ID" in concat_orders.columns else "Seller SKU"
        dedup_cols = [ORDER_KEY, sku_c, "_line_seq"]
        result.orders = (
            concat_orders.drop_duplicates(subset=dedup_cols, keep="first")
            .drop(columns=["_line_seq"], errors="ignore")
            .reset_index(drop=True)
        )
    if raw_order_frames:
        result.raw_orders = pd.concat(raw_order_frames, ignore_index=True).drop_duplicates()
    return result
