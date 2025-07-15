// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Gross Profit Details Consolidated"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "get_query": function() {
                return {
                    query: "erpnext.controllers.queries.customer_query"
                };
            }
        },
        {
            "fieldname": "customer_group",
            "label": __("Customer Group"),
            "fieldtype": "Link",
            "options": "Customer Group"
        },
        {
            "fieldname": "item_code",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function() {
                return {
                    query: "erpnext.controllers.queries.item_query"
                };
            }
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "brand",
            "label": __("Brand"),
            "fieldtype": "Link",
            "options": "Brand"
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    filters: {
                        'company': frappe.query_report.get_filter_value("company")
                    }
                };
            }
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        {
            "fieldname": "sales_person",
            "label": __("Sales Person"),
            "fieldtype": "Link",
            "options": "Sales Person"
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "gross_profit_percent") {
            if (data.gross_profit_percent < 0) {
                value = "<span style='color:red'>" + value + "</span>";
            } else if (data.gross_profit_percent < 10) {
                value = "<span style='color:orange'>" + value + "</span>";
            } else {
                value = "<span style='color:green'>" + value + "</span>";
            }
        }
        
        if (column.fieldname == "gross_profit") {
            if (data.gross_profit < 0) {
                value = "<span style='color:red'>" + value + "</span>";
            } else {
                value = "<span style='color:green'>" + value + "</span>";
            }
        }
        
        if (column.fieldname == "invoice_status") {
            if (data.invoice_status == "Paid") {
                value = "<span class='indicator-pill green'>" + value + "</span>";
            } else if (data.invoice_status == "Unpaid") {
                value = "<span class='indicator-pill orange'>" + value + "</span>";
            } else if (data.invoice_status == "Overdue") {
                value = "<span class='indicator-pill red'>" + value + "</span>";
            }
        }
        
        if (column.fieldname == "delivery_note_status") {
            if (data.delivery_note_status && data.delivery_note_status.includes("Completed")) {
                value = "<span class='indicator-pill green'>" + value + "</span>";
            } else if (data.delivery_note_status && data.delivery_note_status.includes("To Bill")) {
                value = "<span class='indicator-pill orange'>" + value + "</span>";
            }
        }
        
        return value;
    },
    
    onload: function(report) {
        // Add custom buttons
        report.page.add_inner_button(__("Refresh All Data"), function() {
            report.refresh();
        });
        
        report.page.add_inner_button(__("Export Detailed"), function() {
            // Check if report data is available
            if (!report.data || report.data.length === 0) {
                frappe.msgprint(__("No data to export"));
                return;
            }
            
            // Get visible row indices if datatable exists
            let visible_idx = null;
            if (report.datatable && report.datatable.datamanager) {
                visible_idx = report.datatable.datamanager.getFilteredRowIndices();
            }
            
            frappe.call({
                method: 'frappe.desk.query_report.export_query',
                args: {
                    report_name: report.report_name,
                    file_format_type: 'Excel',
                    filters: report.get_values(),
                    visible_idx: visible_idx
                },
                callback: function(r) {
                    if (r.message) {
                        const a = document.createElement('a');
                        a.href = r.message;
                        a.download = report.report_name + '.xlsx';
                        a.click();
                    }
                }
            });
        });
    },
    
    get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true,
            dynamicRowHeight: true,
            inlineFilters: true,
            layout: 'fixed'
        });
    }
};