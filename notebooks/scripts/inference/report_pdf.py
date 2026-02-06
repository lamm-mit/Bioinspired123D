from __future__ import annotations
import os, textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

def generate_run_report(result, log_text, *, wsl_render_base: str, debug_dir: str) -> str:
    render_dir = os.path.dirname(result.get("render_path", "")) or wsl_render_base
    os.makedirs(render_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pdf_path = os.path.join(render_dir, f"Bio3D_RunReport_{timestamp}.pdf")

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Bioinspired3D Core Pipeline Report")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 65, f"Run timestamp: {timestamp}")
    c.drawString(50, height - 80, f"Design prompt: {result.get('design_prompt', 'N/A')}")
    c.line(50, height - 90, width - 50, height - 90)

    summary_y = height - 120
    summary_lines = [
        f"✅ Approved: {result.get('approved')}",
        f"🧩 Blender Status: {result.get('blender_status')}",
        f"🪞 Final Render: {result.get('final_result') or 'N/A'}",
        f"💾 Debug Directory: {debug_dir}",
    ]
    c.setFont("Helvetica", 11)
    for line in summary_lines:
        c.drawString(60, summary_y, line)
        summary_y -= 14

    c.setFont("Courier", 8)
    y = summary_y - 20
    for line in log_text.splitlines():
        if y < 50:
            c.showPage()
            c.setFont("Courier", 8)
            y = height - 50
        c.drawString(50, y, line[:130])
        y -= 9

    final_render = result.get("final_result")
    if final_render and os.path.exists(final_render):
        c.showPage()
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 60, "Final Render Image")
        try:
            img = ImageReader(final_render)
            img_w, img_h = img.getSize()
            aspect = img_h / float(img_w)

            max_width = width * 0.6
            max_height = height * 0.45
            new_w = min(max_width, max_height / aspect)
            new_h = new_w * aspect

            x_offset = (width - new_w) / 2
            y_offset = height - 100 - new_h
            c.drawImage(img, x_offset, y_offset, width=new_w, height=new_h)
        except Exception as e:
            c.setFont("Courier", 9)
            c.drawString(50, height - 120, f"[Image failed to load: {e}]")

    c.save()
    print(f"\n📄 Report saved to: {pdf_path}")
    return pdf_path


def generate_detailed_report(result, log_text, *, wsl_render_base: str) -> str:
    render_dir = os.path.dirname(result.get("render_path", "")) or wsl_render_base
    os.makedirs(render_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pdf_path = os.path.join(render_dir, f"Bio3D_DetailedReport_{timestamp}.pdf")

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, "Bioinspired3D Core — Detailed Run Report")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 75, f"Timestamp: {timestamp}")
    c.drawString(50, height - 88, f"Design prompt: {result.get('design_prompt', 'N/A')}")
    c.line(50, height - 100, width - 50, height - 100)

    c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 60, "Pipeline Transcript (Full Console Output)")
    c.setFont("Courier", 8)
    y = height - 80

    for line in log_text.splitlines():
        if y < 80:
            c.showPage()
            c.setFont("Courier", 8)
            y = height - 60
        c.drawString(50, y, line[:130])
        y -= 9

    pngs = sorted(
        [os.path.join(render_dir, f) for f in os.listdir(render_dir) if f.lower().endswith(".png")],
        key=os.path.getmtime
    )

    if pngs:
        c.showPage()
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 60, "Render Snapshots (Chronological)")
        x_margin = 50
        y = height - 100
        img_size = width * 0.4
        spacing = 20
        col = 0

        for idx, img_path in enumerate(pngs, 1):
            try:
                img = ImageReader(img_path)
                img_w, img_h = img.getSize()
                aspect = img_h / float(img_w)
                new_w = img_size
                new_h = new_w * aspect

                if new_h > height * 0.35:
                    new_h = height * 0.35
                    new_w = new_h / aspect

                x_offset = width / 2 + spacing / 2 if col == 1 else x_margin
                y_offset = y - new_h

                c.drawImage(img, x_offset, y_offset, width=new_w, height=new_h)
                c.setFont("Helvetica", 8)
                c.drawString(x_offset, y_offset - 10, f"Render {idx}: {os.path.basename(img_path)}")

                col += 1
                if col > 1:
                    col = 0
                    y -= (new_h + 60)
                if y < 100:
                    c.showPage()
                    c.setFont("Helvetica", 8)
                    y = height - 100
                    col = 0
            except Exception as e:
                c.setFont("Courier", 8)
                c.drawString(50, y, f"[Image failed to load: {img_path} | {e}]")
                y -= 20

    c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 60, "Vision-Language Model (VLM) Feedback")
    c.setFont("Courier", 8)
    y = height - 80
    vlm_json = result.get("vlm_feedback") or "No VLM feedback found."
    for line in textwrap.wrap(vlm_json, 120):
        if y < 50:
            c.showPage()
            c.setFont("Courier", 8)
            y = height - 50
        c.drawString(50, y, line)
        y -= 9

    c.save()
    print(f"\n📘 Detailed report saved to: {pdf_path}")
    return pdf_path
