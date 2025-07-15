# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, cstr

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    summary = get_summary_data(data)
    
    return columns, data, None, chart, summary

def get_columns():
    return [
        {"fieldname": "sales_invoice_id", "label": _("Sales Invoice ID"), "fieldtype": "Link", "options": "Sales Invoice", "width": 130},
        {"fieldname": "delivery_note_id", "label": _("Delivery Note ID"), "fieldtype": "Data", "width": 200},
        {"fieldname": "invoice_date", "label": _("Invoice Date"), "fieldtype": "Date", "width": 120},
        {"fieldname": "delivery_date", "label": _("Delivery Date"), "fieldtype": "Date", "width": 120},
        {"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 300},
        {"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 400},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 100},
        {"fieldname": "sales_invoice_qty", "label": _("SI Qty"), "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "delivery_note_qty", "label": _("DN Qty"), "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "selling_amount", "label": _("Selling Amount"), "fieldtype": "Currency", "width": 110},
        {"fieldname": "cost_of_goods_sold", "label": _("COGS Amount"), "fieldtype": "Currency", "width": 110},
        {"fieldname": "gross_profit", "label": _("Gross Profit Amount"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "gross_profit_percent", "label": _("Gross Profit %"), "fieldtype": "Percent", "precision": 2, "width": 110},
        {"fieldname": "invoice_status", "label": _("SI Status"), "fieldtype": "Data", "width": 100},
        {"fieldname": "delivery_note_status", "label": _("DN Status"), "fieldtype": "Data", "width": 100},
        {"fieldname": "update_stock", "label": _("Update Stock"), "fieldtype": "Data", "width": 120}
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    query = """
        SELECT
            si.name as sales_invoice_id,
            IFNULL(GROUP_CONCAT(DISTINCT dni.parent), '') as delivery_note_id,
            si.posting_date as invoice_date,
            IFNULL(MAX(dn.posting_date), '') as delivery_date,
            si.customer_name,
            sii.item_code,
            sii.item_name,
            sii.warehouse,
            sii.qty as sales_invoice_qty,
            IFNULL(SUM(dni.qty), 0) as delivery_note_qty,
            sii.amount as selling_amount,
            0 as cost_of_goods_sold,
            0 as gross_profit,
            0 as gross_profit_percent,
            si.status as invoice_status,
            IFNULL(GROUP_CONCAT(DISTINCT dn.status), '') as delivery_note_status,
            CASE WHEN si.update_stock = 1 THEN 'Yes' ELSE 'No' END as update_stock
        FROM
            `tabSales Invoice` si
        INNER JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        LEFT JOIN
            `tabDelivery Note Item` dni ON dni.against_sales_invoice = si.name 
            AND dni.item_code = sii.item_code
            AND dni.docstatus = 1
        LEFT JOIN
            `tabDelivery Note` dn ON dn.name = dni.parent 
            AND dn.docstatus = 1
            AND dn.status != 'Cancelled'
        WHERE
            si.docstatus = 1
            {conditions}
        GROUP BY
            si.name, sii.item_code, sii.idx
        ORDER BY
            si.posting_date DESC, si.name, sii.idx
    """.format(conditions=conditions)
    
    data = frappe.db.sql(query, filters, as_dict=True)
    
    for row in data:
        row.delivery_note_id = row.delivery_note_id or ''
        row.delivery_date = row.delivery_date or ''
        row.delivery_note_status = row.delivery_note_status or ''
        
        if row.update_stock == 'Yes':
            row.cost_of_goods_sold = get_cogs_from_stock_ledger(
                row.sales_invoice_id, row.item_code, row.warehouse, row.sales_invoice_qty
            )
        else:
            row.cost_of_goods_sold = get_cogs_from_delivery_note(
                row.delivery_note_id, row.item_code, row.sales_invoice_qty
            )
        
        row.gross_profit = flt(row.selling_amount) - flt(row.cost_of_goods_sold)
        row.gross_profit_percent = (row.gross_profit / row.selling_amount * 100) if row.selling_amount else 0
        
        row.sales_invoice_qty = flt(row.sales_invoice_qty, 2)
        row.delivery_note_qty = flt(row.delivery_note_qty, 2)
        row.selling_amount = flt(row.selling_amount, 2)
        row.cost_of_goods_sold = flt(row.cost_of_goods_sold, 2)
        row.gross_profit = flt(row.gross_profit, 2)
        row.gross_profit_percent = flt(row.gross_profit_percent, 2)
        
        if row.delivery_note_id and ',' in row.delivery_note_id:
            row.delivery_note_id = row.delivery_note_id.replace(',', ', ')
        if row.delivery_note_status and ',' in row.delivery_note_status:
            row.delivery_note_status = row.delivery_note_status.replace(',', ', ')
    
    if data:
        total_row = {
            "sales_invoice_id": "Total",
            "delivery_note_id": "",
            "invoice_date": "",
            "delivery_date": "",
            "customer_name": "",
            "item_code": "",
            "item_name": "",
            "warehouse": "",
            "sales_invoice_qty": sum(d["sales_invoice_qty"] for d in data),
            "delivery_note_qty": sum(d["delivery_note_qty"] for d in data),
            "selling_amount": sum(d["selling_amount"] for d in data),
            "cost_of_goods_sold": sum(d["cost_of_goods_sold"] for d in data),
            "gross_profit": sum(d["gross_profit"] for d in data),
            "gross_profit_percent": (sum(d["gross_profit"] for d in data) / sum(d["selling_amount"] for d in data) * 100) if sum(d["selling_amount"] for d in data) else 0,
            "invoice_status": "",
            "delivery_note_status": "",
            "update_stock": ""
        }
        data.append(total_row)
    
    return data

def get_chart_data(data):
    customer_profit = {}
    for row in data:
        if row.get("sales_invoice_id") != "Total":
            customer = row.get("customer_name") or "Unknown"
            customer_profit[customer] = customer_profit.get(customer, 0) + flt(row.get("gross_profit"))
    
    labels = list(customer_profit.keys())
    values = list(customer_profit.values())
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Gross Profit",
                    "values": values
                }
            ]
        },
        "type": "bar",
        "colors": ["#28a745"]
    }

def get_summary_data(data):
    total_row = next((row for row in data if row.get("sales_invoice_id") == "Total"), {})
    return [
        {
            "label": _("Total Selling Amount"),
            "value": frappe.format(total_row.get("selling_amount", 0), {"fieldtype": "Currency"}),
            "indicator": "blue"
        },
        {
            "label": _("Total COGS"),
            "value": frappe.format(total_row.get("cost_of_goods_sold", 0), {"fieldtype": "Currency"}),
            "indicator": "orange"
        },
        {
            "label": _("Total Gross Profit"),
            "value": frappe.format(total_row.get("gross_profit", 0), {"fieldtype": "Currency"}),
            "indicator": "green"
        },
        {
            "label": _("Gross Profit %"),
            "value": frappe.format(total_row.get("gross_profit_percent", 0), {"fieldtype": "Percent"}),
            "indicator": "purple"
        }
    ]

def get_cogs_from_stock_ledger(sales_invoice, item_code, warehouse, qty):
    cogs_amount = frappe.db.sql("""
        SELECT SUM(ABS(stock_value_difference)) as total_cogs
        FROM `tabStock Ledger Entry`
        WHERE voucher_type = 'Sales Invoice'
        AND voucher_no = %s
        AND item_code = %s
        AND warehouse = %s
        AND actual_qty < 0
    """, (sales_invoice, item_code, warehouse))
    return flt(cogs_amount[0][0]) if cogs_amount and cogs_amount[0][0] else flt(qty) * get_valuation_rate(item_code, warehouse)

def get_cogs_from_delivery_note(delivery_note_ids, item_code, qty):
    if not delivery_note_ids:
        return 0
    dn_list = delivery_note_ids.split(',') if delivery_note_ids else []
    total_cogs = 0
    for dn in dn_list:
        dn = dn.strip()
        if dn:
            cogs_amount = frappe.db.sql("""
                SELECT SUM(ABS(stock_value_difference)) as total_cogs
                FROM `tabStock Ledger Entry`
                WHERE voucher_type = 'Delivery Note'
                AND voucher_no = %s
                AND item_code = %s
                AND actual_qty < 0
            """, (dn, item_code))
            total_cogs += flt(cogs_amount[0][0]) if cogs_amount and cogs_amount[0][0] else 0
    return total_cogs if total_cogs > 0 else flt(qty) * get_valuation_rate(item_code, frappe.db.get_value("Delivery Note Item", {"parent": dn_list[0] if dn_list else "", "item_code": item_code}, "warehouse"))

def get_valuation_rate(item_code, warehouse):
    valuation_rate = frappe.db.sql("""
        SELECT valuation_rate
        FROM `tabBin`
        WHERE item_code = %s AND warehouse = %s
    """, (item_code, warehouse))
    return flt(valuation_rate[0][0]) if valuation_rate and valuation_rate[0][0] else flt(frappe.db.get_value("Item", item_code, "valuation_rate") or 0)

def get_conditions(filters):
    conditions = []
    if filters.get("company"): conditions.append("si.company = %(company)s")
    if filters.get("from_date"): conditions.append("si.posting_date >= %(from_date)s")
    if filters.get("to_date"): conditions.append("si.posting_date <= %(to_date)s")
    if filters.get("customer"): conditions.append("si.customer = %(customer)s")
    if filters.get("customer_group"): conditions.append("si.customer_group = %(customer_group)s")
    if filters.get("item_code"): conditions.append("sii.item_code = %(item_code)s")
    if filters.get("item_group"): conditions.append("sii.item_group = %(item_group)s")
    if filters.get("warehouse"): conditions.append("sii.warehouse = %(warehouse)s")
    if filters.get("brand"): conditions.append("sii.brand = %(brand)s")
    if filters.get("territory"): conditions.append("si.territory = %(territory)s")
    if filters.get("sales_person"): conditions.append("EXISTS (SELECT 1 FROM `tabSales Team` st WHERE st.parent = si.name AND st.sales_person = %(sales_person)s)")
    return " AND " + " AND ".join(conditions) if conditions else ""