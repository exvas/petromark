import frappe


def execute():
    """
    One-time backfill: set sales_person on Payment Entries that are missing it,
    by fetching from the linked Sales Invoice's Sales Team.
    """
    # Get all PEs without sales_person that have SI references
    pe_names = frappe.db.sql("""
        SELECT DISTINCT pe.name
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per
            ON per.parent = pe.name
            AND per.reference_doctype = 'Sales Invoice'
        WHERE (pe.sales_person IS NULL OR pe.sales_person = '')
        AND pe.docstatus != 2
    """, as_dict=True)

    total = len(pe_names)
    updated = 0
    skipped = 0

    print(f"Found {total} Payment Entries missing sales_person")

    for row in pe_names:
        pe_name = row.name

        # Get the first SI linked to this PE
        si_name = frappe.db.get_value(
            "Payment Entry Reference",
            {"parent": pe_name, "reference_doctype": "Sales Invoice"},
            "reference_name",
            order_by="idx asc",
        )

        if not si_name:
            skipped += 1
            continue

        # Get sales_person from SI Sales Team
        sales_person = frappe.db.get_value(
            "Sales Team",
            {"parent": si_name, "parenttype": "Sales Invoice"},
            "sales_person",
            order_by="idx asc",
        )

        if not sales_person:
            print(f"  SKIP {pe_name}: no sales_person in SI {si_name}")
            skipped += 1
            continue

        # Update directly (bypasses submit restriction, works for all docstatus)
        frappe.db.set_value("Payment Entry", pe_name, "sales_person", sales_person, update_modified=False)
        print(f"  SET  {pe_name} → {sales_person} (from SI {si_name})")
        updated += 1

    frappe.db.commit()
    print(f"\nDone. Updated: {updated}, Skipped: {skipped}, Total: {total}")
