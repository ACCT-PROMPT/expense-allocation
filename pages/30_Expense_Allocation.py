import sys
import os
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import style

st.set_page_config(page_title="ปันส่วนค่าใช้จ่าย", page_icon="📅")
style.inject()
style.back_home()
st.title("📅 ปันส่วนค่าใช้จ่าย / ค่าบริการจ่ายล่วงหน้า")
st.write("คำนวณการปันส่วนค่าใช้จ่ายรายปี สำหรับสัญญาที่คาบเกี่ยวหลายรอบบัญชี")


def count_days(start: date, end: date) -> int:
    """นับจำนวนวัน: ถ้าวันเดิมกันต่างปี = นับเป็นปีเต็ม (365/366), ไม่งั้น end - start + 1"""
    if start.month == end.month and start.day == end.day:
        # วันชนวัน → นับเป็นจำนวนวันในปีนั้นๆ ทั้งหมดรวมกัน
        total = 0
        y = start.year
        while y < end.year:
            total += 366 if _is_leap(y) else 365
            y += 1
        return total
    else:
        return (end - start).days + 1


def _is_leap(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _days_in_year(year: int) -> int:
    return 366 if _is_leap(year) else 365


def allocate(start: date, end: date, amount: float, acct_end_month: int, acct_end_day: int):
    """แตกยอดรายปีบัญชี"""
    total_days = count_days(start, end)
    if total_days == 0:
        return [], 0

    rows = []
    remaining_amount = amount
    cursor = start

    while cursor <= end:
        # หาวันสิ้นสุดรอบบัญชีของปีนี้
        acct_year_end = date(cursor.year, acct_end_month, acct_end_day)
        # ถ้าวันเริ่มต้นอยู่หลังวันสิ้นสุดรอบบัญชีของปีนั้น → ใช้ปีถัดไป
        if cursor > acct_year_end:
            acct_year_end = date(cursor.year + 1, acct_end_month, acct_end_day)

        # วันสุดท้ายของช่วงนี้ = น้อยกว่าระหว่างสิ้นสุดสัญญา กับ สิ้นสุดรอบบัญชี
        period_end = min(end, acct_year_end)

        # นับวันของช่วงนี้
        if cursor.month == period_end.month and cursor.day == period_end.day:
            period_days = _days_in_year(cursor.year)
        else:
            period_days = (period_end - cursor).days + 1

        # คำนวณยอด (ปัดเศษ 2 ตำแหน่ง ยกเว้นงวดสุดท้าย)
        is_last = period_end >= end
        if is_last:
            period_amount = remaining_amount
        else:
            period_amount = round(amount * period_days / total_days, 2)
            remaining_amount -= period_amount

        rows.append({
            "รอบบัญชี": f"{cursor.strftime('%d/%m/%Y')} – {period_end.strftime('%d/%m/%Y')}",
            "ปี": cursor.year,
            "_start": cursor,
            "_end": period_end,
            "จำนวนวัน": period_days,
            "ยอด ex-VAT (บาท)": period_amount,
        })

        if period_end >= end:
            break
        cursor = period_end + timedelta(days=1)

    return rows, total_days


# ── UI ──────────────────────────────────────────────────────────────────────

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("วันที่เริ่มต้นบริการ", value=date.today(), format="DD/MM/YYYY")
with col2:
    end_date = st.date_input("วันที่สิ้นสุดบริการ", value=date(date.today().year + 1, date.today().month, date.today().day), format="DD/MM/YYYY")

col3, col4 = st.columns(2)
with col3:
    amount = st.number_input("มูลค่าก่อน VAT (บาท)", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
with col4:
    use_custom_acct_end = st.checkbox("กำหนดวันสิ้นสุดรอบบัญชีเอง (ค่าเริ่มต้น: 31/12)")

if use_custom_acct_end:
    acct_end = st.date_input("วันสิ้นสุดรอบบัญชี", value=date(date.today().year, 12, 31), format="DD/MM/YYYY")
    acct_end_month = acct_end.month
    acct_end_day = acct_end.day
else:
    acct_end_month = 12
    acct_end_day = 31

col5, col6 = st.columns(2)
with col5:
    assess_date = st.date_input(
        "ณ วันที่ประเมิน (ดูยอด ณ วันที่...)",
        value=date(date.today().year, acct_end_month, acct_end_day),
        format="DD/MM/YYYY",
        help="ยอดค่าใช้จ่ายสะสมถึงวันนี้ vs ยอด Prepaid คงเหลือหลังจากวันนี้",
    )

st.divider()

if st.button("คำนวณ", type="primary", use_container_width=True):
    if start_date > end_date:
        st.error("วันที่เริ่มต้นต้องไม่มากกว่าวันที่สิ้นสุด")
    elif amount <= 0:
        st.error("กรุณากรอกมูลค่าก่อน VAT ให้ถูกต้อง")
    else:
        result, total_days = allocate(start_date, end_date, amount, acct_end_month, acct_end_day)

        st.subheader("สรุปการปันส่วน")

        m1, m2, m3 = st.columns(3)
        m1.metric("จำนวนวันรวม", f"{total_days:,} วัน")
        m2.metric("มูลค่ารวม ex-VAT", f"{amount:,.2f} บาท")
        m3.metric("จำนวนรอบบัญชี", f"{len(result)} รอบ")

        st.divider()

        df = pd.DataFrame(result)

        # แยกรอบที่ period_end <= assess_date ว่าเป็นค่าใช้จ่ายแล้ว
        # รอบที่ period_start > assess_date ว่าเป็น Prepaid ทั้งก้อน
        # รอบที่คาบ assess_date → แยกตามสัดส่วนวัน
        # หารอบที่ assess_date อยู่ใน, รอบก่อนหน้า, และรอบหลัง
        current_period = None
        prepaid_rows = []

        for r in result:
            r_start = r["_start"]
            r_end = r["_end"]
            if r_start <= assess_date <= r_end:
                current_period = r
            elif r_start > assess_date:
                prepaid_rows.append(r)

        prepaid_amount = round(sum(r["ยอด ex-VAT (บาท)"] for r in prepaid_rows), 2)
        prepaid_days = sum(r["จำนวนวัน"] for r in prepaid_rows)

        c1, c2 = st.columns(2)
        with c1:
            if current_period:
                st.info(
                    f"**ค่าใช้จ่ายรอบ {current_period['รอบบัญชี']}**\n\n"
                    f"{current_period['จำนวนวัน']:,} วัน → **{current_period['ยอด ex-VAT (บาท)']:,.2f} บาท**"
                )
            else:
                st.info("ไม่มีรอบบัญชีที่ตรงกับวันที่ประเมิน")
        with c2:
            if prepaid_amount > 0:
                st.warning(
                    f"**ค่าบริการจ่ายล่วงหน้า (Prepaid) หลัง {assess_date.strftime('%d/%m/%Y')}**\n\n"
                    f"{prepaid_days:,} วัน → **{prepaid_amount:,.2f} บาท**"
                )
            else:
                st.success("ไม่มียอด Prepaid คงเหลือ ณ วันที่ประเมิน")

        st.subheader("รายละเอียดรายรอบบัญชี")

        # จัด format ตาราง (ซ่อน column internal _start/_end)
        display_df = df[["รอบบัญชี", "จำนวนวัน", "ยอด ex-VAT (บาท)"]].copy()
        display_df["จำนวนวัน"] = display_df["จำนวนวัน"].apply(lambda x: f"{x:,}")
        display_df["ยอด ex-VAT (บาท)"] = display_df["ยอด ex-VAT (บาท)"].apply(lambda x: f"{x:,.2f}")

        # เพิ่มแถว Total
        total_row = pd.DataFrame([{
            "รอบบัญชี": "รวมทั้งหมด",
            "จำนวนวัน": f"{total_days:,}",
            "ยอด ex-VAT (บาท)": f"{amount:,.2f}",
        }])
        display_df = pd.concat([display_df, total_row], ignore_index=True)

        st.dataframe(display_df, use_container_width=True, hide_index=True)
