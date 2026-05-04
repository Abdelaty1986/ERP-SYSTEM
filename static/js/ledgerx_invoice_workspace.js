(function () {
    function formatMoney(value) {
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(value || 0));
    }

    function toNumber(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function setSummaryValue(element, value) {
        const nextText = formatMoney(value);
        if (element.textContent === nextText) {
            return;
        }
        element.textContent = nextText;
        element.classList.remove("is-updated");
        void element.offsetWidth;
        element.classList.add("is-updated");
        window.setTimeout(() => element.classList.remove("is-updated"), 260);
    }

    function buildRowHtml() {
        return `
            <tr>
                <td>
                    <select name="product_id[]" class="form-select product-select" required>
                        <option value="">اختر الصنف</option>
                    </select>
                </td>
                <td>
                    <select name="unit_id[]" class="form-select unit-select" data-selected-unit="" required>
                        <option value="">اختر الوحدة</option>
                    </select>
                    <span class="invoice-meta-text unit-meta">معامل التحويل: 1.0000</span>
                </td>
                <td>
                    <input type="number" step="0.01" min="0.01" name="quantity[]" class="form-control quantity-input" required>
                    <span class="invoice-row-feedback"></span>
                </td>
                <td>
                    <input type="number" step="0.01" min="0.01" name="unit_price[]" class="form-control price-input" required>
                    <span class="invoice-row-feedback"></span>
                </td>
                <td class="invoice-tax-cell">
                    <div class="invoice-switch">
                        <input type="checkbox" class="vat-checkbox" checked>
                        <span>VAT</span>
                    </div>
                    <input type="hidden" name="vat_applicable[]" class="vat-flag" value="1">
                    <input type="number" step="0.01" min="0" name="vat_rate[]" value="14" class="form-control invoice-rate-input vat-rate-input">
                </td>
                <td class="invoice-tax-cell">
                    <div class="invoice-switch">
                        <input type="checkbox" class="withholding-checkbox">
                        <span>خصم وإضافة</span>
                    </div>
                    <input type="hidden" name="withholding_applicable[]" class="withholding-flag" value="0">
                    <input type="number" step="0.01" min="0" name="withholding_rate[]" value="0" class="form-control invoice-rate-input withholding-rate-input">
                </td>
                <td><span class="invoice-readonly line-subtotal">0.00</span></td>
                <td><span class="invoice-readonly line-vat">0.00</span></td>
                <td><span class="invoice-readonly line-withholding">0.00</span></td>
                <td><span class="invoice-readonly line-net">0.00</span></td>
                <td class="text-center no-print">
                    <button type="button" class="btn btn-outline-danger btn-sm remove-line">حذف</button>
                </td>
            </tr>
        `;
    }

    function populateProducts(row, products) {
        const productSelect = row.querySelector(".product-select");
        if (productSelect.options.length > 1) {
            return;
        }
        products.forEach((product) => {
            const option = document.createElement("option");
            option.value = product.id;
            option.textContent = product.label;
            productSelect.appendChild(option);
        });
    }

    function syncUnitOptions(row, config, forceDefault) {
        const productSelect = row.querySelector(".product-select");
        const unitSelect = row.querySelector(".unit-select");
        const priceInput = row.querySelector(".price-input");
        const unitMeta = row.querySelector(".unit-meta");
        const productMeta = config.productUnitsMap[String(productSelect.value)] || null;
        const selectedUnit = unitSelect.dataset.selectedUnit || "";
        unitSelect.innerHTML = '<option value="">اختر الوحدة</option>';
        if (!productMeta || !productMeta.units.length) {
            unitMeta.textContent = "معامل التحويل: 1.0000";
            return;
        }
        productMeta.units.forEach((unit) => {
            const option = document.createElement("option");
            option.value = unit.unit_id;
            option.textContent = `${unit.unit_name} x ${unit.conversion_factor}`;
            option.dataset.conversionFactor = unit.conversion_factor || 1;
            option.dataset.price = config.purpose === "purchase" ? (unit.purchase_price || "") : (unit.sale_price || "");
            if (String(unit.unit_id) === String(selectedUnit || (forceDefault ? productMeta.default_unit_id : selectedUnit))) {
                option.selected = true;
            }
            unitSelect.appendChild(option);
        });
        if (!unitSelect.value && productMeta.default_unit_id) {
            unitSelect.value = String(productMeta.default_unit_id);
        }
        const selectedOption = unitSelect.selectedOptions[0];
        unitMeta.textContent = `معامل التحويل: ${toNumber(selectedOption?.dataset?.conversionFactor || 1).toFixed(4)}`;
        if (!priceInput.value && selectedOption?.dataset?.price) {
            priceInput.value = selectedOption.dataset.price;
        }
    }

    function recalcRow(row) {
        const qty = toNumber(row.querySelector(".quantity-input").value);
        const price = toNumber(row.querySelector(".price-input").value);
        const vatChecked = row.querySelector(".vat-checkbox").checked;
        const withholdingChecked = row.querySelector(".withholding-checkbox").checked;
        const vatRate = vatChecked ? toNumber(row.querySelector(".vat-rate-input").value) : 0;
        const withholdingRate = withholdingChecked ? toNumber(row.querySelector(".withholding-rate-input").value) : 0;
        const subtotal = +(qty * price).toFixed(2);
        const vatAmount = +(subtotal * vatRate / 100).toFixed(2);
        const withholdingAmount = +(subtotal * withholdingRate / 100).toFixed(2);
        const lineNet = +(subtotal + vatAmount - withholdingAmount).toFixed(2);

        row.querySelector(".vat-flag").value = vatChecked ? "1" : "0";
        row.querySelector(".withholding-flag").value = withholdingChecked ? "1" : "0";
        row.querySelector(".vat-rate-input").disabled = !vatChecked;
        row.querySelector(".withholding-rate-input").disabled = !withholdingChecked;

        row.querySelector(".line-subtotal").textContent = formatMoney(subtotal);
        row.querySelector(".line-vat").textContent = formatMoney(vatAmount);
        row.querySelector(".line-withholding").textContent = formatMoney(withholdingAmount);
        row.querySelector(".line-net").textContent = formatMoney(lineNet);

        const qtyFeedback = row.querySelectorAll(".invoice-row-feedback")[0];
        const priceFeedback = row.querySelectorAll(".invoice-row-feedback")[1];
        const qtyInvalid = row.querySelector(".quantity-input").value !== "" && qty <= 0;
        const priceInvalid = row.querySelector(".price-input").value !== "" && price <= 0;
        qtyFeedback.textContent = qtyInvalid ? "الكمية يجب أن تكون أكبر من صفر." : "";
        priceFeedback.textContent = priceInvalid ? "السعر يجب أن يكون أكبر من صفر." : "";
        row.classList.toggle("invoice-row-error", qtyInvalid || priceInvalid);

        return { subtotal, vatAmount, withholdingAmount, lineNet };
    }

    function recalcSummary(config) {
        const rows = Array.from(config.table.querySelectorAll("tbody tr"));
        const totals = rows.reduce((acc, row) => {
            const result = recalcRow(row);
            acc.subtotal += result.subtotal;
            acc.vat += result.vatAmount;
            acc.withholding += result.withholdingAmount;
            acc.net += result.lineNet;
            return acc;
        }, { subtotal: 0, vat: 0, withholding: 0, net: 0 });

        setSummaryValue(config.summary.subtotal, totals.subtotal);
        setSummaryValue(config.summary.vat, totals.vat);
        setSummaryValue(config.summary.withholding, totals.withholding);
        setSummaryValue(config.summary.net, totals.net);
    }

    function bindRow(row, config, forceDefault) {
        populateProducts(row, config.products);
        syncUnitOptions(row, config, forceDefault);
        recalcRow(row);
    }

    window.initInvoiceWorkspace = function initInvoiceWorkspace(config) {
        config.table = document.getElementById(config.tableId);
        config.summary = {
            subtotal: document.getElementById(config.summaryIds.subtotal),
            vat: document.getElementById(config.summaryIds.vat),
            withholding: document.getElementById(config.summaryIds.withholding),
            net: document.getElementById(config.summaryIds.net),
        };

        Array.from(config.table.querySelectorAll("tbody tr")).forEach((row) => bindRow(row, config, false));

        config.table.addEventListener("change", (event) => {
            const row = event.target.closest("tr");
            if (!row) {
                return;
            }
            if (event.target.classList.contains("product-select")) {
                row.querySelector(".unit-select").dataset.selectedUnit = "";
                if (!row.querySelector(".price-input").dataset.edited) {
                    row.querySelector(".price-input").value = "";
                }
                syncUnitOptions(row, config, true);
            }
            if (event.target.classList.contains("unit-select")) {
                event.target.dataset.selectedUnit = event.target.value;
                syncUnitOptions(row, config, false);
            }
            recalcSummary(config);
        });

        config.table.addEventListener("input", (event) => {
            const row = event.target.closest("tr");
            if (!row) {
                return;
            }
            if (event.target.classList.contains("price-input")) {
                event.target.dataset.edited = "1";
            }
            recalcSummary(config);
        });

        config.table.addEventListener("click", (event) => {
            if (!event.target.classList.contains("remove-line")) {
                return;
            }
            const rows = config.table.querySelectorAll("tbody tr");
            if (rows.length > 1) {
                event.target.closest("tr").remove();
                recalcSummary(config);
            }
        });

        document.getElementById(config.addButtonId).addEventListener("click", () => {
            const tbody = config.table.querySelector("tbody");
            const wrapper = document.createElement("tbody");
            wrapper.innerHTML = buildRowHtml();
            const row = wrapper.firstElementChild;
            bindRow(row, config, true);
            tbody.appendChild(row);
            recalcSummary(config);
        });

        recalcSummary(config);
    };
})();
