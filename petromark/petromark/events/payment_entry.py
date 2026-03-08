import frappe


def set_sales_person_from_invoice(doc, method):
    """
    Fetch Sales Person from the linked Sales Invoice's Sales Team
    and set it on the Payment Entry's sales_person field.
    This is a local feature for Petromark - runs on Payment Entry before_insert.
    """
    if doc.sales_person:
        return  # Already set, nothing to do

    # Find the first Sales Invoice reference
    si_name = None
    for ref in doc.references:
        if ref.reference_doctype == "Sales Invoice":
            si_name = ref.reference_name
            break

    if not si_name:
        return

    # Fetch sales_person from SI's Sales Team
    sales_person = frappe.db.get_value(
        "Sales Team",
        {"parent": si_name, "parenttype": "Sales Invoice"},
        "sales_person",
        order_by="idx asc",
    )

    if sales_person:
        doc.sales_person = sales_person
