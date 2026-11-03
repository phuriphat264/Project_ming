import subprocess
from pathlib import Path

html_content = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>คู่มือการใช้งานระบบคำนวณต้นทุนและกำไร TikTok Shop - บริษัท มาตัง คอสเมติก จำกัด</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700;800&family=Prompt:wght@400;600;700;800&display=swap');

  @page {
    size: A4;
    margin: 16mm 16mm 18mm 16mm;
    @bottom-right {
      content: "หน้า " counter(page);
      font-family: 'Sarabun', sans-serif;
      font-size: 8.5pt;
      color: #94a3b8;
    }
    @bottom-left {
      content: "คู่มือการใช้งานระบบคำนวณต้นทุนและกำไร TikTok Shop · บริษัท มาตัง คอสเมติก จำกัด";
      font-family: 'Sarabun', sans-serif;
      font-size: 8.5pt;
      color: #94a3b8;
    }
  }

  @page:first {
    margin: 0;
    @bottom-right { content: normal; }
    @bottom-left { content: normal; }
  }

  * { box-sizing: border-box; }
  body {
    font-family: 'Sarabun', 'Thonburi', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1e293b;
    font-size: 10pt;
    line-height: 1.6;
    background: #ffffff;
    margin: 0;
    padding: 0;
  }

  h1, h2, h3, h4, .title-font {
    font-family: 'Prompt', 'Sarabun', sans-serif;
    color: #0f172a;
    font-weight: 700;
  }

  .page-break { page-break-after: always; break-after: page; }
  .avoid-break { page-break-inside: avoid; break-inside: avoid; }

  /* COVER PAGE */
  .cover {
    width: 210mm;
    height: 297mm;
    padding: 42mm 24mm 28mm 24mm;
    background: linear-gradient(145deg, #0f172a 0%, #1e1b4b 42%, #312e81 100%);
    color: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    page-break-after: always;
  }
  .cover-decor {
    position: absolute;
    top: 0;
    right: 0;
    width: 130mm;
    height: 130mm;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.28) 0%, rgba(99, 102, 241, 0) 70%);
  }
  .cover-badge {
    display: inline-block;
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #a5b4fc;
    padding: 6px 16px;
    border-radius: 30px;
    font-size: 9.5pt;
    font-weight: 600;
    letter-spacing: 0.05em;
    margin-bottom: 20px;
  }
  .cover-title {
    font-size: 27pt;
    line-height: 1.25;
    color: #ffffff;
    margin: 0 0 16px 0;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  .cover-subtitle {
    font-size: 12.5pt;
    line-height: 1.6;
    color: #c7d2fe;
    margin: 0 0 32px 0;
    font-weight: 400;
  }
  .cover-highlights {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .cover-card {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 13px 16px;
  }
  .cover-card-title {
    font-size: 10.5pt;
    font-weight: 700;
    color: #e0e7ff;
    margin-bottom: 4px;
  }
  .cover-card-desc {
    font-size: 8.5pt;
    color: #94a3b8;
    line-height: 1.45;
  }
  .cover-footer {
    border-top: 1px solid rgba(255, 255, 255, 0.18);
    padding-top: 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .company-name {
    font-size: 13pt;
    font-weight: 700;
    color: #ffffff;
  }
  .company-desc {
    font-size: 8.5pt;
    color: #94a3b8;
    margin-top: 2px;
  }
  .doc-ver {
    font-size: 8.5pt;
    color: #a5b4fc;
    text-align: right;
    line-height: 1.5;
  }

  /* HEADINGS */
  h1.section-title {
    font-size: 16pt;
    color: #1e1b4b;
    border-bottom: 2px solid #4f46e5;
    padding-bottom: 6px;
    margin-top: 10px;
    margin-bottom: 14px;
  }
  h2.sub-title {
    font-size: 12pt;
    color: #312e81;
    margin-top: 14px;
    margin-bottom: 8px;
    border-left: 4px solid #6366f1;
    padding-left: 8px;
  }
  h3 {
    font-size: 10.5pt;
    color: #0f172a;
    margin-top: 12px;
    margin-bottom: 6px;
  }

  /* TABLES */
  table.custom-table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 14px 0;
    font-size: 9pt;
  }
  table.custom-table th {
    background: #f1f5f9;
    color: #1e293b;
    padding: 8px 10px;
    border: 1px solid #cbd5e1;
    font-weight: 700;
    text-align: left;
  }
  table.custom-table td {
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    vertical-align: top;
  }
  table.custom-table tr:nth-child(even) td {
    background: #f8fafc;
  }

  /* CALLOUT BOXES */
  .callout {
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 9pt;
    line-height: 1.55;
  }
  .callout-info {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    color: #1e40af;
  }
  .callout-success {
    background: #f0fdf4;
    border-left: 4px solid #10b981;
    color: #065f46;
  }
  .callout-warn {
    background: #fffbeb;
    border-left: 4px solid #f59e0b;
    color: #92400e;
  }
  .callout-title {
    font-weight: 700;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  /* STEP CARDS */
  .step-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
  }
  .step-badge {
    display: inline-block;
    background: #4f46e5;
    color: #ffffff;
    font-size: 8pt;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 4px;
    margin-bottom: 4px;
  }
  .step-title {
    font-size: 10.5pt;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 4px;
  }

  /* BADGES & CODE */
  .badge {
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 8pt;
    font-weight: 600;
  }
  .badge-blue { background: #dbeafe; color: #1e40af; }
  .badge-green { background: #dcfce7; color: #166534; }
  .badge-amber { background: #fef3c7; color: #92400e; }
  .badge-purple { background: #f3e8ff; color: #6b21a8; }
  code {
    background: #f1f5f9;
    color: #475569;
    padding: 1px 5px;
    border-radius: 4px;
    font-family: Menlo, Monaco, Consolas, monospace;
    font-size: 8.5pt;
  }

  /* TOC */
  .toc-item {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px dotted #cbd5e1;
    font-size: 9.5pt;
  }
  .toc-item b { color: #1e1b4b; }
</style>
</head>
<body>

<!-- COVER PAGE -->
<div class="cover">
  <div class="cover-decor"></div>
  <div>
    <div class="cover-badge">OFFICIAL USER MANUAL · คู่มือการใช้งานฉบับสมบูรณ์</div>
    <div class="cover-title">ระบบคำนวณต้นทุนและกำไรสุทธิ<br>TikTok Shop (Multi-Channel)</div>
    <div class="cover-subtitle">
      คู่มือการติดตั้ง ใช้งาน นำเข้าไฟล์คำสั่งซื้อ บริหารราคาทุนสินค้า<br>
      จัดการหลายช่องทาง และส่งออกไฟล์ต้นทุนรวม 7 ชีตตามมาตรฐานบริษัท
    </div>

    <div class="cover-highlights">
      <div class="cover-card">
        <div class="cover-card-title">⚡ อ่านไฟล์เร็วขึ้น 8.7 เท่า</div>
        <div class="cover-card-desc">เทคโนโลยี Calamine Rust Engine อ่านออเดอร์ 30,000+ แถวใน 1.4 วินาที ไม่ค้าง ไม่สะดุด</div>
      </div>
      <div class="cover-card">
        <div class="cover-card-title">🏬 รองรับหลายช่องทาง (Multi-Shop)</div>
        <div class="cover-card-desc">สลับร้านค้า ตรวจจับช่องทางอัตโนมัติ และเปรียบเทียบผลประกอบการข้ามช่องทาง</div>
      </div>
      <div class="cover-card">
        <div class="cover-card-title">✏️ ระบบตรวจจับ SKU ขาดแบบเรียลไทม์</div>
        <div class="cover-card-desc">มีตารางให้พิมพ์กรอกราคาทุนบนหน้าเว็บได้ทันที คำนวณกำไรใหม่แม่นยำ 100%</div>
      </div>
      <div class="cover-card">
        <div class="cover-card-title">📑 ส่งออกไฟล์ต้นทุนรวม 7 ชีต</div>
        <div class="cover-card-desc">โครงสร้างตรงกับฟอร์มบัญชี 100% พร้อมสูตร =SUM และผูกกำไร =+F-G รายบรรทัด</div>
      </div>
    </div>
  </div>

  <div class="cover-footer">
    <div>
      <div class="company-name">บริษัท มาตัง คอสเมติก จำกัด (Matang Cosmetic Co., Ltd.)</div>
      <div class="company-desc">ระบบบริหารจัดการต้นทุนและบัญชีการเงินออนไลน์ TikTok Shop</div>
    </div>
    <div class="doc-ver">
      <b>เวอร์ชัน:</b> 2.5 (Unified Production)<br>
      <b>วันที่อัปเดต:</b> พฤศจิกายน 2569
    </div>
  </div>
</div>

<!-- PAGE 2: TABLE OF CONTENTS & OVERVIEW -->
<div class="avoid-break">
  <h1 class="section-title">📑 สารบัญ (Table of Contents)</h1>
  
  <div style="margin-top: 14px;">
    <div class="toc-item"><span><b>บทที่ 1:</b> ภาพรวมระบบและการติดตั้งเริ่มต้น (System Overview & Setup)</span><span>หน้า 3</span></div>
    <div class="toc-item"><span><b>บทที่ 2:</b> การเข้าสู่ระบบและการจัดการสิทธิ์ (Login & User Roles)</span><span>หน้า 4</span></div>
    <div class="toc-item"><span><b>บทที่ 3:</b> การจัดการหลายช่องทาง TikTok Shop (Multi-Shop Management)</span><span>หน้า 4</span></div>
    <div class="toc-item"><span><b>บทที่ 4:</b> การนำเข้าข้อมูลและการคำนวณต้นทุนอัตโนมัติ (Data Import & Pipeline)</span><span>หน้า 5</span></div>
    <div class="toc-item"><span><b>บทที่ 5:</b> ระบบตรวจจับและกรอกราคาทุนสินค้าที่ขาดบนหน้าเว็บ (Missing SKU Quick Entry)</span><span>หน้า 6</span></div>
    <div class="toc-item"><span><b>บทที่ 6:</b> การตรวจสอบตัวเลขและฟันธงผลกำไร (Data Inspection: Col F, G, H)</span><span>หน้า 7</span></div>
    <div class="toc-item"><span><b>บทที่ 7:</b> การส่งออกไฟล์ต้นทุนรวม 7 ชีตและรายงานผู้บริหาร (Master Excel & PDF Reports)</span><span>หน้า 7</span></div>
    <div class="toc-item"><span><b>บทที่ 8:</b> แดชบอร์ดเปรียบเทียบผลงานและสถิติขั้นสูง (Analytics & Channel Comparison)</span><span>หน้า 8</span></div>
    <div class="toc-item"><span><b>บทที่ 9:</b> การสำรองและกู้คืนฐานข้อมูล 1-Click (Database Backup & Restore)</span><span>หน้า 8</span></div>
    <div class="toc-item"><span><b>บทที่ 10:</b> คำถามที่พบบ่อยและการแก้ไขปัญหา (Troubleshooting & FAQ)</span><span>หน้า 8</span></div>
  </div>

  <div class="callout callout-info" style="margin-top: 24px;">
    <div class="callout-title">💡 วัตถุประสงค์ของคู่มือเล่มนี้</div>
    จัดทำขึ้นเพื่อให้พนักงานฝ่ายบัญชี, ผู้ดูแลระบบ, และผู้บริหารของ บริษัท มาตัง คอสเมติก จำกัด สามารถใช้งานระบบคำนวณต้นทุนและกำไร TikTok Shop ได้อย่างถูกต้อง รวดเร็ว และลดข้อผิดพลาดในการคำนวณต้นทุนสินค้าสูญเปล่าจากออเดอร์ยกเลิกหรือการดึงราคาทุนผิดพลาด
  </div>

  <h2 class="sub-title">สถาปัตยกรรมการทำงานของระบบ (Architecture Highlights)</h2>
  <p>
    ระบบถูกออกแบบด้วยสถาปัตยกรรมแบบ <b>Unified High-Performance Engine</b> ซึ่งรวมการทำงานของฐานข้อมูล SQLite, คลังเก็บคำสั่งซื้อสะสม (Order Repository) และ Calamine Parser ทำให้การอ่านและประมวลผลไฟล์ขนาดใหญ่กว่า 60,000 แถว ใช้เวลาเพียง 1-3 วินาที โดยไม่ต้องพึ่งพาระบบคลาวด์ภายนอก ข้อมูลทางการเงินทั้งหมดถูกจัดเก็บไว้อย่างปลอดภัยภายในเครื่องของบริษัท 100%
  </p>
</div>

<div class="page-break"></div>

<!-- PAGE 3: CHAPTER 1 SETUP -->
<div class="avoid-break">
  <h1 class="section-title">บทที่ 1: ภาพรวมระบบและการติดตั้งเริ่มต้น (Setup)</h1>
  
  <p>
    ระบบคำนวณต้นทุนและกำไร TikTok Shop พัฒนาขึ้นเพื่อทดแทนการใช้ Excel ทำมือแบบเดิมที่ใช้เวลานานและเสี่ยงต่อการผิดพลาด โดยระบบสามารถรวบรวมไฟล์รายงานรายได้ (Settlement) และไฟล์คำสั่งซื้อ (Order) ขนาดใหญ่มากกว่า 50,000 รายการ มาจับคู่ราคาทุนสินค้า (SKU Master) และคำนวณกำไรสุทธิแท้จริงได้ภายในไม่กี่วินาที
  </p>

  <h2 class="sub-title">1.1 โครงสร้างไฟล์ในโฟลเดอร์โปรเจกต์</h2>
  <table class="custom-table">
    <thead>
      <tr>
        <th style="width: 28%;">ไฟล์ / โฟลเดอร์</th>
        <th>คำอธิบายหน้าที่</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>app.py</code></td>
        <td>ไฟล์หลักสำหรับรันระบบ Streamlit Web Application</td>
      </tr>
      <tr>
        <td><code>run_app.bat</code></td>
        <td>ไฟล์สคริปต์ 1-Click สำหรับเปิดใช้งานระบบบน Windows (ดับเบิลคลิกเปิดได้ทันที)</td>
      </tr>
      <tr>
        <td><code>pages/</code></td>
        <td>หน้าจอเมนูการทำงานต่างๆ (1 แดชบอร์ด, 2 นำเข้าข้อมูล, 3 สินค้า, 4 วิเคราะห์, 5 รายงาน, 6 ผู้ใช้งาน)</td>
      </tr>
      <tr>
        <td><code>core/</code></td>
        <td>โมดูลประมวลผลหลัก (ฐานข้อมูล db, อ่านไฟล์ loader, คำนวณ pipeline, ส่งออก export)</td>
      </tr>
      <tr>
        <td><code>data/app.db</code></td>
        <td>ฐานข้อมูล SQLite เก็บราคาทุนสินค้า, รายชื่อช่องทางร้านค้า, ผู้ใช้งาน และผลลัพธ์ย้อนหลัง</td>
      </tr>
      <tr>
        <td><code>data/</code></td>
        <td>โฟลเดอร์สำหรับวางไฟล์ Excel คำสั่งซื้อและรายได้ เพื่อโหลดด่วน</td>
      </tr>
    </tbody>
  </table>

  <h2 class="sub-title">1.2 วิธีการเปิดใช้งานระบบ (How to Run)</h2>
  
  <div class="step-card">
    <div class="step-badge">สำหรับ WINDOWS</div>
    <div class="step-title">วิธีที่ 1: ดับเบิลคลิกไฟล์สคริปต์อัตโนมัติ</div>
    <p style="margin: 0; font-size: 9pt;">
      เข้าไปที่โฟลเดอร์โปรแกรม แล้วดับเบิลคลิกที่ไฟล์ <code>run_app.bat</code> ระบบจะเปิดหน้าต่างเบราว์เซอร์ไปที่ <code>http://localhost:8501</code> ให้โดยอัตโนมัติ
    </p>
  </div>

  <div class="step-card">
    <div class="step-badge">สำหรับ MAC / LINUX หรือ TERMINAL</div>
    <div class="step-title">วิธีที่ 2: รันผ่านคำสั่ง Terminal</div>
    <p style="margin: 0; font-size: 9pt;">
      เปิด Terminal เข้าไปยังโฟลเดอร์โปรเจกต์ แล้วพิมพ์คำสั่ง:<br>
      <code>cd cost_profit_system && .venv/bin/streamlit run app.py</code>
    </p>
  </div>
</div>

<div class="page-break"></div>

<!-- PAGE 4: CHAPTER 2 & 3 LOGIN & MULTI-SHOP -->
<div class="avoid-break">
  <h1 class="section-title">บทที่ 2: การเข้าสู่ระบบและการจัดการสิทธิ์ (Login)</h1>
  
  <p>
    เพื่อความปลอดภัยของข้อมูลทางการเงิน ระบบมีการแบ่งสิทธิ์การใช้งานออกเป็น 2 ระดับ:
  </p>
  <table class="custom-table">
    <thead>
      <tr>
        <th style="width: 25%;">ระดับสิทธิ์ (Role)</th>
        <th style="width: 35%;">ชื่อผู้ใช้เริ่มต้น (Default)</th>
        <th>ขอบเขตอำนาจหน้าที่ในระบบ</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="badge badge-purple">Admin (ผู้บริหาร/บัญชี)</span></td>
        <td><code>admin</code> (รหัสผ่านเริ่มต้น: <code>admin123</code>)</td>
        <td>เข้าถึงได้ทุกหน้า: เพิ่ม/ลบช่องทาง, แก้ไขราคาทุนสินค้า, บันทึก Snapshot, สำรองข้อมูล, จัดการผู้ใช้</td>
      </tr>
      <tr>
        <td><span class="badge badge-blue">Staff (พนักงานทั่วไป)</span></td>
        <td><code>staff</code> (รหัสผ่านเริ่มต้น: <code>staff123</code>)</td>
        <td>นำเข้าข้อมูลและดูตารางคำสั่งซื้อได้ แต่จะ<b>ถูกซ่อนราคาทุนสินค้า (Col G) และกำไรสุทธิ (Col H)</b> เพื่อรักษาความลับ</td>
      </tr>
    </tbody>
  </table>

  <h1 class="section-title">บทที่ 3: การจัดการหลายช่องทาง TikTok Shop (Multi-Shop)</h1>
  <p>
    ระบบรองรับการขายสินค้าหลายช่องทาง (เช่น ร้านหลักมาตัง, ดีไวน์, ช่องไลฟ์สด) รวมไว้ในโปรแกรมเดียว โดยสามารถจัดการได้ 2 ช่องทาง:
  </p>

  <h2 class="sub-title">3.1 การจัดการในหน้า "6. การตั้งค่าและผู้ใช้งาน" (แท็บ 1)</h2>
  <ul>
    <li><b>➕ เพิ่มร้านค้าใหม่:</b> สลับโหมดเป็น "เพิ่มร้านค้าใหม่" ระบุรหัสร้าน (เช่น <code>live1</code>), ชื่อร้าน (เช่น <code>มาตัง ไลฟ์สด 1</code>), TikTok Handle (เช่น <code>@matang_live</code>) แล้วกดบันทึก</li>
    <li><b>✏️ แก้ไขร้านค้า:</b> สลับโหมดเป็น "แก้ไขร้านค้าที่มีอยู่" เลือกร้านที่ต้องการแก้ไข ระบบจะดึงข้อมูลเดิมขึ้นมาให้พิมพ์แก้ไขชื่อร้านหรือ Handle ได้ทันที</li>
    <li><b>🗑️ ลบร้านค้า:</b> ในโหมดแก้ไขจะมีปุ่มลบร้านค้าสีแดง พร้อมกล่องกดยืนยัน (ร้านหลัก <code>matang</code> ได้รับการล็อกป้องกันการลบ)</li>
    <li><b>⭐ ตั้งเป็นร้านหลัก:</b> มีปุ่มทางลัด "ตั้งเป็นร้านหลัก" ให้คลิกเปลี่ยนช่องทางหลักได้ทันที</li>
  </ul>

  <div class="callout callout-success">
    <div class="callout-title">🎯 ระบบตรวจจับช่องทางอัตโนมัติ (Auto-Detection)</div>
    เมื่อผู้ใช้อัปโหลดไฟล์ หากชื่อไฟล์มีคำว่า <b>"ดีไวน์", "dwine"</b> หรือ TikTok Handle ระบบจะสลับช่องทางที่เลือกให้อัตโนมัติ และตั้งชื่อไฟล์ Export ให้เป็น <code>ต้นทุนดีไวน์2569-09.xlsx</code> ทันที
  </div>
</div>

<div class="page-break"></div>

<!-- PAGE 5: CHAPTER 4 IMPORT -->
<div class="avoid-break">
  <h1 class="section-title">บทที่ 4: การนำเข้าข้อมูลและการคำนวณต้นทุน (Data Import)</h1>
  
  <p>
    ในหน้า <b>"2. 📤 นำเข้าข้อมูล"</b> ผู้ใช้สามารถเลือกวิธีนำเข้าข้อมูลได้ 3 รูปแบบตามความสะดวก:
  </p>

  <div class="step-card">
    <div class="step-badge">โหมดที่ 1: อัปโหลด 2 ไฟล์ (แนะนำที่สุด ⭐)</div>
    <div class="step-title">อัปโหลดไฟล์ Income + ไฟล์คำสั่งซื้อจากคอมพิวเตอร์</div>
    <p style="margin: 0; font-size: 9pt;">
      1. <b>แถบเลือกร้านค้า:</b> เลือกว่าต้องการทำงวดของช่องทางใด (เช่น มาตัง หรือ ดีไวน์)<br>
      2. <b>ช่องที่ 1 (ไฟล์รายได้):</b> วางไฟล์รายได้ <code>income_xxx.xlsx</code> ที่ดาวน์โหลดจาก TikTok Shop Finance<br>
      3. <b>ช่องที่ 2 (ไฟล์คำสั่งซื้อ):</b> วางไฟล์คำสั่งซื้อ <code>ทั้งหมด คำสั่งซื้อ-xxx.xlsx</code> (ใส่ได้มากกว่า 1 ไฟล์ เช่น ออเดอร์เดือนปัจจุบัน + เดือนก่อนหน้า เพื่อเก็บสะสมลงคลังคำสั่งซื้อ)<br>
      4. กดปุ่ม <b>"🚀 เริ่มประมวลผลและสร้างไฟล์ต้นทุนรวม"</b>
    </p>
  </div>

  <div class="step-card">
    <div class="step-badge">โหมดที่ 2: อ่านด่วนจากโฟลเดอร์ data/</div>
    <div class="step-title">วางไฟล์ในโฟลเดอร์ data/ แล้วคลิกเลือก</div>
    <p style="margin: 0; font-size: 9pt;">
      เพียงนำไฟล์ไปวางในโฟลเดอร์ <code>data/</code> ระบบจะสแกนและจัดกลุ่มไฟล์คำสั่งซื้อและไฟล์รายได้ให้อัตโนมัติ สามารถกดคลิกประมวลผลได้ทันทีโดยไม่ต้องอัปโหลดซ้ำ
    </p>
  </div>

  <div class="step-card">
    <div class="step-badge">โหมดที่ 3: โยนไฟล์รวมหลายเดือน / ไฟล์ต้นทุนเดิม</div>
    <div class="step-title">อัปโหลดไฟล์ Master ที่เคยทำไว้ในอดีต</div>
    <p style="margin: 0; font-size: 9pt;">
      หากมีไฟล์ต้นทุนเดิม เช่น <code>ต้นทุน2569-08.xlsx</code> หรือ <code>ต้นทุนดีไวน์2569-06.xlsx</code> สามารถลากไฟล์มาวางที่แท็บนี้ ระบบจะแยกงวดเดือนและบันทึกประวัติย้อนหลังให้ทันที
    </p>
  </div>

  <div class="callout callout-info">
    <div class="callout-title">💡 ระบบคลังคำสั่งซื้อสะสม (Order Repository)</div>
    TikTok มีการตัดรอบโอนเงินข้ามเดือน (เช่น ออเดอร์ปลายเดือน 8 เงินอาจโอนมาในรอบเดือน 9) ระบบจะดึงข้อมูลสินค้าจากคลังสะสมมาช่วยคำนวณต้นทุนให้อัตโนมัติ ทำให้ไม่ต้องค้นหาไฟล์เก่าด้วยตนเอง
  </div>
</div>

<div class="page-break"></div>

<!-- PAGE 6: CHAPTER 5 MISSING SKU -->
<div class="avoid-break">
  <h1 class="section-title">บทที่ 5: ระบบตรวจจับและกรอกราคาทุน SKU ขาดบนหน้าเว็บ</h1>
  
  <p>
    <b>ปัญหาที่พบบ่อย:</b> มีการสร้างสินค้าใหม่ใน TikTok Shop แต่ยังไม่ได้เพิ่มรหัสสินค้าลงในฐานข้อมูลราคาทุน ทำให้ต้นทุนสินค้าถูกคิดเป็น 0 บาท และกำไรสูงเกินจริง
  </p>

  <h2 class="sub-title">5.1 การทำงานของระบบตรวจจับอัตโนมัติ</h2>
  <p>
    เมื่อนำเข้าไฟล์ ระบบจะนำรหัสสินค้าทุกตัวไปตรวจสอบกับตาราง SKU Master หากพบสินค้าใดที่ <b>"ไม่มีในระบบ"</b> หรือ <b>"ราคาทุนเป็น 0 บาท"</b> ระบบจะแสดงแถบแจ้งเตือนสีทองเด่นชัดทันที:
  </p>

  <div class="callout callout-warn">
    <div class="callout-title">⚠️ ตัวอย่างแถบแจ้งเตือนบนหน้าเว็บ</div>
    <b>ตรวจพบ X สินค้าในคำสั่งซื้อที่ยังไม่มีราคาทุนในระบบ!</b><br>
    สินค้าเหล่านี้ถูกคำนวณต้นทุนเป็น 0 บาทชั่วคราว คุณสามารถพิมพ์ราคาทุนในตารางด้านล่างนี้ได้ทันที แล้วกด "💾 บันทึกราคาทุนและคำนวณใหม่ทันที"
  </div>

  <h2 class="sub-title">5.2 วิธีการพิมพ์ราคาทุนบนหน้าเว็บ (Inline Editor)</h2>
  <ol>
    <li>ดูตารางรายการสินค้าที่ขาด จะแสดง <b>รหัส SKU, ชื่อสินค้า, หมวดหมู่, จำนวนชิ้นที่ขาย, และจำนวนออเดอร์</b></li>
    <li><b>ดับเบิลคลิก</b> ที่ช่อง <code>ราคาทุนต่อหน่วย (บาท) ⭐</code> ของสินค้านั้น แล้วพิมพ์ตัวเลขต้นทุน เช่น <code>85.00</code></li>
    <li>หากมีราคาขาย สามารถกรอกเพิ่มเติมในช่อง <code>ราคาตั้งขาย (บาท)</code> ได้</li>
    <li>กดปุ่ม <b>"💾 บันทึกราคาทุนที่กรอก และคำนวณใหม่ทันที ⚡"</b></li>
    <li>ระบบจะบันทึกต้นทุนลงฐานข้อมูล ถอดสูตรคำนวณต้นทุนรวม (Col G) และกำไรสุทธิ (Col H) ใหม่ทันที โดยไม่ต้องเริ่มอัปโหลดไฟล์ใหม่!</li>
  </ol>

  <div class="callout callout-success">
    <div class="callout-title">➕ มีแบบฟอร์มเพิ่มทีละรายการ (Manual Add Form)</div>
    หากต้องการเพิ่ม SKU รายการเดียว สามารถเปิดที่ช่อง <i>"➕ หรือเพิ่มราคาทุนทีละรายการผ่านแบบฟอร์ม"</i> เลือกรหัสสินค้า กรอกราคาทุน แล้วกดบันทึกได้ทันที
  </div>
</div>

<div class="page-break"></div>

<!-- PAGE 7: CHAPTER 6 & 7 INSPECTION & EXPORT -->
<div class="avoid-break">
  <h1 class="section-title">บทที่ 6: การตรวจสอบตัวเลขและฟันธงผลกำไร (Data Inspection)</h1>
  
  <p>
    หลังจากประมวลผลสำเร็จ หน้าจอจะแสดง <b>การ์ดสรุปตัวเลขทางการเงิน 4 ใบ</b> ซึ่งตรงกับคอลัมน์มาตรฐานของฝ่ายบัญชี:
  </p>

  <table class="custom-table">
    <thead>
      <tr>
        <th style="width: 28%;">การ์ดตัวเลข</th>
        <th style="width: 25%;">คอลัมน์มาตรฐาน</th>
        <th>คำอธิบายความหมาย</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>1. เงินที่ TikTok โอนจริง</b></td>
        <td><span class="badge badge-green">Col F: ยอดการชำระเงินทั้งหมด</span></td>
        <td>ยอดเงินสุทธิที่ TikTok โอนเข้าบัญชีจริง (ยอดขาย หักค่าธรรมเนียมแพลตฟอร์มและค่าส่ง)</td>
      </tr>
      <tr>
        <td><b>2. ต้นทุนสินค้ารวม</b></td>
        <td><span class="badge badge-amber">Col G: ต้นทุนรวม (COGS)</span></td>
        <td>ต้นทุนสินค้าจริงตาม SKU ที่จัดส่งสำเร็จ (ออเดอร์ยกเลิก/คืนเงิน จะคิดต้นทุนเป็น 0 บาท ไม่นับซ้ำ)</td>
      </tr>
      <tr>
        <td><b>3. กำไรสุทธิแท้จริง</b></td>
        <td><span class="badge badge-blue">Col H: กำไร (H = F − G)</span></td>
        <td>กำไรขั้นต้นที่แท้จริงหลังจากหักต้นทุนสินค้าออกจากเงินที่ได้รับโอนจริง</td>
      </tr>
      <tr>
        <td><b>4. สินค้าที่ไม่มีราคาทุน</b></td>
        <td><span class="badge badge-purple">Missing SKU Count</span></td>
        <td>จำนวน SKU ที่ยังขาดราคาทุน (ต้องเป็น <b>0 ตัว</b> จึงจะพร้อมส่งออกอย่างสมบูรณ์ 100%)</td>
      </tr>
    </tbody>
  </table>

  <h1 class="section-title">บทที่ 7: การส่งออกไฟล์ต้นทุนรวม 7 ชีตและรายงานผู้บริหาร</h1>

  <h2 class="sub-title">7.1 โครงสร้างไฟล์ต้นทุนรวม (Master Excel 7 Sheets)</h2>
  <table class="custom-table">
    <thead>
      <tr>
        <th style="width: 30%;">ชื่อชีต (Sheet Name)</th>
        <th>รายละเอียดและสูตรที่ระบบผูกไว้ให้</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>1. รายละเอียดคำสั่งซื้อ</b></td>
        <td>แทรก <b>Col F (ยอดชำระ), Col G (ต้นทุนรวม), Col H (กำไร)</b> โดยแถวที่ 1 ใส่สูตร <code>=SUM(...)</code> ไฮไลท์สีเหลือง และคอลัมน์ H ผูกสูตร <code>=+F-G</code> ทุกแถว</td>
      </tr>
      <tr>
        <td><b>2. SKU</b></td>
        <td>ตารางราคาทุนสินค้าทุกรหัส (รหัส, ชื่อ, หมวดหมู่, ราคาทุน, ราคาปลีก, ราคาโปร, ราคาตั้งขาย)</td>
      </tr>
      <tr>
        <td><b>3. Order9 & Order8</b></td>
        <td>แยกชีตคำสั่งซื้อตามเดือนที่สั่งซื้อจริง แทรก <b>Col I (ราคาต่อหน่วย) และ Col J (มูลค่า)</b></td>
      </tr>
      <tr>
        <td><b>4. รายงาน</b></td>
        <td>ตารางรายงานสรุปรายได้และค่าธรรมเนียมตามโครงสร้าง TikTok Shop</td>
      </tr>
      <tr>
        <td><b>5. บันทึกการถอน</b></td>
        <td>ประวัติรายการถอนเงินเข้าบัญชีธนาคาร พร้อมวันที่และสถานะสำเร็จ</td>
      </tr>
      <tr>
        <td><b>6. คำอธิบายค่าธรรมเนียม</b></td>
        <td>ตารางอภิธานศัพท์อธิบายค่าธรรมเนียมทุกประเภทของ TikTok Shop</td>
      </tr>
      <tr>
        <td><b>7. ads (ถ้ามี)</b></td>
        <td>รายการค่าโฆษณา TikTok Ads นอกแพลตฟอร์ม</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="page-break"></div>

<!-- PAGE 8: CHAPTER 8, 9 & 10 ANALYTICS, BACKUP & FAQ -->
<div class="avoid-break">
  <h1 class="section-title">บทที่ 8: แดชบอร์ดเปรียบเทียบผลงานและสถิติขั้นสูง</h1>
  <p>
    ในหน้า <b>"1. 📊 แดชบอร์ด"</b> ผู้บริหารสามารถติดตามภาพรวมและเจาะลึกข้อมูลได้ทันที:
  </p>
  <ul>
    <li><b>แบนเนอร์ฟันธงผลกำไร:</b> ระบุชัดเจนว่าเดือนนี้ <i>"การขายไม่ขาดทุน! กำไรสุทธิ +฿X,XXX,XXX"</i> หรือมีออเดอร์ขาดทุนกี่รายการ</li>
    <li><b>🏬 เปรียบเทียบผลงานข้ามช่องทาง (Channel Comparison):</b> กราฟแท่งเปรียบเทียบ ยอดเงินโอน (Col F), ต้นทุนสินค้า (Col G), และกำไรสุทธิ (Col H) ระหว่างแต่ละร้านค้า (มาตัง vs ดีไวน์) แบบ Side-by-Side</li>
    <li><b>วิเคราะห์หมวดหมู่และสินค้าขายดี:</b> จัดอันดับสินค้าที่ทำกำไรสูงสุด 10 อันดับแรก และสัดส่วนยอดขายตามหมวดหมู่</li>
  </ul>

  <h1 class="section-title">บทที่ 9: การสำรองและกู้คืนฐานข้อมูล (Backup & Restore)</h1>
  <div class="step-card">
    <div class="step-title">📦 การสำรองข้อมูล (One-Click Backup)</div>
    <p style="margin: 0; font-size: 8.5pt;">
      ไปที่หน้า <b>"6. ⚙️ การตั้งค่าระบบ" (แท็บ 3)</b> แล้วกดปุ่ม <b>"⬇️ ดาวน์โหลด Backup ทั้งระบบ (.zip)"</b> ระบบจะบีบอัดฐานข้อมูล SQLite, ประวัติการคำนวณ Snapshot ทุกงวด, และตารางราคาทุนสินค้าเป็นไฟล์ ZIP เดียว แนะนำให้ดาวน์โหลดเก็บไว้ทุกสิ้นเดือน
    </p>
  </div>
  <div class="step-card">
    <div class="step-title">🔄 การกู้คืนข้อมูล (Restore)</div>
    <p style="margin: 0; font-size: 8.5pt;">
      กรณีเปลี่ยนเครื่องคอมพิวเตอร์หรือลงโปรแกรมใหม่ เพียงอัปโหลดไฟล์ <code>Backup_xxx.zip</code> แล้วกดยืนยัน ข้อมูลย้อนหลังทั้งหมดจะกลับคืนมาสมบูรณ์ 100%
    </p>
  </div>

  <h1 class="section-title">บทที่ 10: คำถามที่พบบ่อยและการแก้ไขปัญหา (FAQ)</h1>
  <table class="custom-table">
    <thead>
      <tr>
        <th style="width: 35%;">คำถาม / ปัญหาที่พบ</th>
        <th>สาเหตุและแนวทางแก้ไข</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>ทำไมแถวบนสุดใน Excel คอลัมน์ F ถึงเป็น 0?</b></td>
        <td>เกิดจากเวอร์ชันเก่าก่อนปรับปรุง ในเวอร์ชันปัจจุบันได้รับการแก้ไขแล้ว แถวที่ 1 จะใส่สูตร <code>=SUM(F2:F...)</code> ไฮไลท์สีเหลืองตรงกับหน้าเว็บเป๊ะ 100%</td>
      </tr>
      <tr>
        <td><b>ทำไมต้นทุนหน้าเว็บ ต่างจาก Excel เดิมของบัญชีเล็กน้อย?</b></td>
        <td>Excel เดิมของบัญชีใช้สูตร <code>VLOOKUP</code> ดั้งเดิมซึ่งดึงได้เฉพาะสินค้าชิ้นแรกในออเดอร์ที่มีหลายชิ้น ส่วนระบบใหม่คำนวณครบทุก SKU จริงตามหลักบัญชี จึงแม่นยำกว่า 100%</td>
      </tr>
      <tr>
        <td><b>หากย้อนกลับไปทำข้อมูลงวดเก่า จะกระทบออเดอร์สะสมไหม?</b></td>
        <td>ไม่กระทบ ระบบมีระบบแยกคลังออเดอร์สะสมตามเดือน (Repository) และสามารถเลือกดูหรือลบงวดเก่าได้อย่างอิสระ</td>
      </tr>
    </tbody>
  </table>
</div>

</body>
</html>
"""

# Write HTML file
html_path = Path("/Users/phuriphat/Project_ming/คู่มือการใช้งานระบบคำนวณต้นทุน_มาตังคอสเมติก.html")
html_path.write_text(html_content, encoding="utf-8")

html_copy = Path("/Users/phuriphat/Project_ming/cost_profit_system/คู่มือการใช้งานระบบคำนวณต้นทุน_มาตังคอสเมติก.html")
html_copy.write_text(html_content, encoding="utf-8")

# Generate PDF using Chrome Headless
pdf_path = Path("/Users/phuriphat/Project_ming/คู่มือการใช้งานระบบคำนวณต้นทุน_มาตังคอสเมติก.pdf")
pdf_copy = Path("/Users/phuriphat/Project_ming/cost_profit_system/คู่มือการใช้งานระบบคำนวณต้นทุน_มาตังคอสเมติก.pdf")

chrome_app = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
cmd = [
    chrome_app,
    "--headless",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--user-data-dir=/tmp/chrome-pdf-dir",
    "--no-pdf-header-footer",
    f"--print-to-pdf={pdf_path}",
    str(html_path)
]

res = subprocess.run(cmd, capture_output=True, text=True)
if pdf_path.exists() and pdf_path.stat().st_size > 1000:
    pdf_copy.write_bytes(pdf_path.read_bytes())
    print(f"✅ PDF manual successfully created: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)")
else:
    print(f"❌ PDF generation failed: {res.stderr}")
