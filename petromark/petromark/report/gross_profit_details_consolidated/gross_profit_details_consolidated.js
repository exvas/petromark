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
            "options": "Customer"
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
            "get_query": () => ({query: "erpnext.controllers.queries.item_query"})
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
            "get_query": () => ({filters: {"company": frappe.query_report.get_filter_value("company")}})
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
        
        if (column.fieldname == "gross_profit_percent" && data) {
            if (data.gross_profit_percent < 0) value = "<span style='color:red'>" + value + "</span>";
            else if (data.gross_profit_percent < 10) value = "<span style='color:orange'>" + value + "</span>";
            else value = "<span style='color:green'>" + value + "</span>";
        }
        
        if (column.fieldname == "gross_profit" && data) {
            if (data.gross_profit < 0) value = "<span style='color:red'>" + value + "</span>";
            else value = "<span style='color:green'>" + value + "</span>";
        }
        
        if (column.fieldname == "invoice_status" && data) {
            if (data.invoice_status == "Paid") value = "<span class='indicator-pill green' style='background-color: transparent; padding: 2px 8px;'>" + value + "</span>";
            else if (data.invoice_status == "Unpaid") value = "<span class='indicator-pill orange' style='background-color: transparent; padding: 2px 8px;'>" + value + "</span>";
            else if (data.invoice_status == "Overdue") value = "<span class='indicator-pill red' style='background-color: transparent; padding: 2px 8px;'>" + value + "</span>";
        }
        
        if (column.fieldname == "delivery_note_status" && data) {
            if (data.delivery_note_status && data.delivery_note_status.includes("Completed")) value = "<span class='indicator-pill green' style='background-color: transparent; padding: 2px 8px;'>" + value + "</span>";
            else if (data.delivery_note_status && data.delivery_note_status.includes("To Bill")) value = "<span class='indicator-pill orange' style='background-color: transparent; padding: 2px 8px;'>" + value + "</span>";
        }
        
        return value;
    },
    
    "onload": function(report) {
        $('<style>')
            .prop('type', 'text/css')
            .html(`
                .dt-scrollable { overflow-x: auto !important; }
                .report-wrapper { overflow: visible !important; }
                .datatable { font-size: 12px; }
                .dt-cell__content {
                    padding: 4px 8px;
                    background-color: transparent !important;
                    border: none !important;
                    min-width: 0 !important;
                }
                .dt-row:hover .dt-cell__content { background-color: #f0f0f0 !important; }
                .dt-cell__content:focus, .dt-cell__content:active { background-color: transparent !important; outline: none !important; }
                .dt-row.selected .dt-cell__content { background-color: transparent !important; }
                .indicator-pill {
                    background-color: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                    display: inline-block;
                    padding: 2px 8px;
                }
                .indicator-pill.green { color: #28a745 !important; }
                .indicator-pill.orange { color: #fd7e14 !important; }
                .indicator-pill.red { color: #dc3545 !important; }
                .dt-col { 
                    min-width: 150px !important;
                    max-width: none !important;
                }
                .dt-header {
                    white-space: nowrap !important;
                    min-width: 150px !important;
                }
                .datatable .dt-row { min-width: fit-content !important; }
                .summary-container {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 15px;
                    margin-bottom: 20px;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .summary-card {
                    flex: 1;
                    min-width: 200px;
                    padding: 10px;
                    background-color: #fff;
                    border-radius: 6px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    text-align: center;
                }
                .summary-card h4 {
                    margin: 0;
                    font-size: 14px;
                    color: #333;
                }
                .summary-card p {
                    margin: 5px 0 0;
                    font-size: 18px;
                    font-weight: bold;
                }
                .chart-container {
                    margin-bottom: 20px;
                    padding: 15px;
                    background-color: #fff;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                #gross-profit-chart {
                    max-width: 100%;
                    height: 400px;
                }
            `)
            .appendTo('head');
        
        report.page.add_inner_button(__("Refresh All Data"), () => report.refresh());
        report.page.add_inner_button(__("Export Detailed"), () => {
            if (!report.data || report.data.length === 0) {
                frappe.msgprint(__("No data to export"));
                return;
            }
            let visible_idx = report.datatable?.datamanager?.getFilteredRowIndices() || null;
            frappe.call({
                method: 'frappe.desk.query_report.export_query',
                args: {report_name: report.report_name, file_format_type: 'Excel', filters: report.get_values(), visible_idx},
                callback: function(r) { if (r.message) { const a = document.createElement('a'); a.href = r.message; a.download = report.report_name + '.xlsx'; a.click(); } }
            });
        });

        report.page.add_inner_button(__("Toggle Chart"), () => {
            const chartContainer = $("#gross-profit-chart-container");
            chartContainer.toggle();
        });

        report.render_summary_and_chart = function() {
            const wrapper = $(report.wrapper);
            wrapper.find(".summary-container, .chart-container").remove();

            if (report.summary && report.summary.length) {
                const summaryHtml = `
                    <div class="summary-container">
                        ${report.summary.map(s => `
                            <div class="summary-card">
                                <h4>${s.label}</h4>
                                <p style="color: ${s.indicator}">${s.value}</p>
                            </div>
                        `).join('')}
                    </div>
                `;
                wrapper.prepend(summaryHtml);
            }

            if (report.chart && report.chart.data && report.chart.data.labels.length) {
                const chartHtml = `
                    <div class="chart-container" id="gross-profit-chart-container">
                        <canvas id="gross-profit-chart"></canvas>
                    </div>
                `;
                wrapper.prepend(chartHtml);
            }
        };

        const original_make = report.make;
        report.make = function() {
            original_make.call(report);
            report.render_summary_and_chart();
        };
    },
    
    "get_datatable_options": function(options) {
        return Object.assign(options, {
            checkboxColumn: true,
            dynamicRowHeight: true,
            inlineFilters: true,
            cellHeight: 35,
            noDataMessage: __('No Data'),
            disableReorderColumn: false,
            events: { onCheckRow: () => {} }
        });
    }
};