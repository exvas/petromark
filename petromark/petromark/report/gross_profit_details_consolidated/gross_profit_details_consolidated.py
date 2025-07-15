# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, cstr


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "sales_invoice_id",
            "label": _("Sales Invoice ID"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 140
        },
        {
            "fieldname": "delivery_note_id",
            "label": _("Delivery Note ID"),
            "fieldtype": "Link",
            "options": "Delivery Note",
            "width": 140
        },
        {
            "fieldname": "invoice_date",
            "label": _("Invoice Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "delivery_date",
            "label": _("Delivery Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer Name"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 180
        },
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "warehouse",
            "label": _("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "fieldname": "sales_invoice_qty",
            "label": _("Sales Invoice Qty"),
            "fieldtype": "Float",
            "precision": 2,
            "width": 120
        },
        {
            "fieldname": "delivery_note_qty",
            "label": _("Delivery Note Qty"),
            "fieldtype": "Float",
            "precision": 2,
            "width": 120
        },
        {
            "fieldname": "selling_amount",
            "label": _("Selling Amount"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "cost_of_goods_sold",
            "label": _("Cost of Goods Sold Amount"),
            "fieldtype": "Currency",
            "width": 160
        },
        {
            "fieldname": "gross_profit",
            "label": _("Gross Profit Amount"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "gross_profit_percent",
            "label": _("Gross Profit %"),
            "fieldtype": "Percent",
            "precision": 2,
            "width": 110
        },
        {
            "fieldname": "invoice_status",
            "label": _("Invoice Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "delivery_note_status",
            "label": _("Delivery Note Status"),
            "fieldtype": "Data",
            "width": 140
        },
        {
            "fieldname": "update_stock",
            "label": _("Update Stock"),
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    
    query = """
        SELECT
            si.name as sales_invoice_id,
            GROUP_CONCAT(DISTINCT dni.parent) as delivery_note_id,
            si.posting_date as invoice_date,
            MAX(dn.posting_date) as delivery_date,
            si.customer_name,
            sii.item_code,
            sii.item_name,
            sii.item_group,
            sii.warehouse,
            sii.qty as sales_invoice_qty,
            SUM(IFNULL(dni.qty, 0)) as delivery_note_qty,
            sii.amount as selling_amount,
            0 as cost_of_goods_sold,
            0 as gross_profit,
            0 as gross_profit_percent,
            si.status as invoice_status,
            GROUP_CONCAT(DISTINCT dn.status) as delivery_note_status,
            CASE WHEN si.update_stock = 1 THEN 'Yes' ELSE 'No' END as update_stock,
            si.company,
            sii.name as si_detail
        FROM
            `tabSales Invoice` si
        INNER JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        LEFT JOIN
            `tabDelivery Note Item` dni ON dni.against_sales_invoice = si.name 
            AND dni.item_code = sii.item_code
        LEFT JOIN
            `tabDelivery Note` dn ON dn.name = dni.parent AND dn.docstatus = 1
        WHERE
            si.docstatus = 1
            {conditions}
        GROUP BY
            si.name, sii.item_code, sii.idx
        ORDER BY
            si.posting_date DESC, si.name, sii.idx
    """.format(conditions=conditions)
    
    data = frappe.db.sql(query, filters, as_dict=True)
    
    # Calculate COGS for each row
    for row in data:
        # Get actual COGS based on stock ledger entries or delivery note
        if row.update_stock == 'Yes':
            # If update_stock is Yes, get COGS from stock ledger entries
            row.cost_of_goods_sold = get_cogs_from_stock_ledger(
                row.sales_invoice_id, 
                row.item_code, 
                row.warehouse,
                row.sales_invoice_qty
            )
        else:
            # If update_stock is No, get COGS from linked delivery notes
            row.cost_of_goods_sold = get_cogs_from_delivery_note(
                row.delivery_note_id,
                row.item_code,
                row.sales_invoice_qty
            )
        
        # Calculate gross profit
        row.gross_profit = flt(row.selling_amount) - flt(row.cost_of_goods_sold)
        
        # Calculate gross profit percentage
        if row.selling_amount > 0:
            row.gross_profit_percent = (row.gross_profit / row.selling_amount) * 100
        else:
            row.gross_profit_percent = 0
        
        # Process delivery note IDs
        if row.delivery_note_id and ',' in row.delivery_note_id:
            row.delivery_note_id = row.delivery_note_id.replace(',', ', ')
        if row.delivery_note_status and ',' in row.delivery_note_status:
            row.delivery_note_status = row.delivery_note_status.replace(',', ', ')
    
    return data


def get_cogs_from_stock_ledger(sales_invoice, item_code, warehouse, qty):
    """Get COGS from Stock Ledger Entry for Sales Invoice with Update Stock"""
    cogs_amount = frappe.db.sql("""
        SELECT 
            SUM(ABS(stock_value_difference)) as total_cogs
        FROM 
            `tabStock Ledger Entry`
        WHERE 
            voucher_type = 'Sales Invoice'
            AND voucher_no = %s
            AND item_code = %s
            AND warehouse = %s
            AND actual_qty < 0
    """, (sales_invoice, item_code, warehouse))
    
    if cogs_amount and cogs_amount[0][0]:
        return flt(cogs_amount[0][0])
    
    # Fallback to valuation rate if no stock ledger entry found
    valuation_rate = get_valuation_rate(item_code, warehouse)
    return flt(qty) * flt(valuation_rate)


def get_cogs_from_delivery_note(delivery_note_ids, item_code, qty):
    """Get COGS from Delivery Note Stock Ledger Entries"""
    if not delivery_note_ids:
        return 0
    
    # Handle multiple delivery notes
    dn_list = delivery_note_ids.split(',') if delivery_note_ids else []
    
    total_cogs = 0
    for dn in dn_list:
        dn = dn.strip()
        if dn:
            cogs_amount = frappe.db.sql("""
                SELECT 
                    SUM(ABS(stock_value_difference)) as total_cogs
                FROM 
                    `tabStock Ledger Entry`
                WHERE 
                    voucher_type = 'Delivery Note'
                    AND voucher_no = %s
                    AND item_code = %s
                    AND actual_qty < 0
            """, (dn, item_code))
            
            if cogs_amount and cogs_amount[0][0]:
                total_cogs += flt(cogs_amount[0][0])
    
    if total_cogs > 0:
        return total_cogs
    
    # Fallback to valuation rate
    warehouse = frappe.db.get_value("Delivery Note Item", 
        {"parent": dn_list[0] if dn_list else "", "item_code": item_code}, 
        "warehouse")
    valuation_rate = get_valuation_rate(item_code, warehouse)
    return flt(qty) * flt(valuation_rate)


def get_valuation_rate(item_code, warehouse):
    """Get current valuation rate for item in warehouse"""
    valuation_rate = frappe.db.sql("""
        SELECT 
            valuation_rate
        FROM 
            `tabBin`
        WHERE 
            item_code = %s 
            AND warehouse = %s
    """, (item_code, warehouse))
    
    if valuation_rate and valuation_rate[0][0]:
        return flt(valuation_rate[0][0])
    
    # If no bin record, get from item master
    return frappe.db.get_value("Item", item_code, "valuation_rate") or 0


def get_conditions(filters):
    conditions = []
    
    if filters.get("company"):
        conditions.append("si.company = %(company)s")
    
    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
    
    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
    
    if filters.get("customer_group"):
        conditions.append("si.customer_group = %(customer_group)s")
    
    if filters.get("item_code"):
        conditions.append("sii.item_code = %(item_code)s")
    
    if filters.get("item_group"):
        conditions.append("sii.item_group = %(item_group)s")
    
    if filters.get("warehouse"):
        conditions.append("sii.warehouse = %(warehouse)s")
    
    if filters.get("brand"):
        conditions.append("sii.brand = %(brand)s")
    
    if filters.get("territory"):
        conditions.append("si.territory = %(territory)s")
    
    if filters.get("sales_person"):
        conditions.append("""EXISTS (
            SELECT 1 FROM `tabSales Team` st 
            WHERE st.parent = si.name AND st.sales_person = %(sales_person)s
        )""")
    
    return " AND " + " AND ".join(conditions) if conditions else ""