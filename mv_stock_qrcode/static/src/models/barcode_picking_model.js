/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";


patch(BarcodePickingModel.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    setData() {
        super.setData(...arguments);
    },

    // GETTER

    get useExistingMoveLines() {
        return true;
    },

    // --------------------------------------------------------------------------
    // Private
    // --------------------------------------------------------------------------

    async _processBarcode(barcode) {
        const codeScanning = barcode;
        const operation_type = this.config.operation_type || '';

        let codeScanningData = {};
        let currentLine = false;
        // Creates a filter if needed, which can help to get the right record
        // when multiple records have the same model and barcode.
        const filters = {};
        if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
            filters['stock.lot'] = {
                product_id: this.selectedLine.product_id.id,
            };
        }
        try {
            codeScanningData = await this._parseBarcode(codeScanning, filters);
            if (this._shouldSearchForAnotherLot(codeScanningData, filters)) {
                // Retry to parse the barcode without filters in case it matches an existing
                // record that can't be found because of the filters
                const lot = await this.cache.getRecordByBarcode(codeScanningData, 'stock.lot');
                if (lot) {
                    Object.assign(codeScanningData, { lot, match: true });
                }
            }
        } catch (parseErrorMessage) {
            codeScanningData.error = parseErrorMessage;
        }

        // Keep in memory every scans.
        this.scanHistory.unshift(codeScanningData);

        // Makes flash the screen if the scanned QRcode was recognized.
        if (codeScanningData.match) {
            this.trigger('flash');
        }

        // Process each data in order, starting with non-ambiguous data type.
        // As action is always a single data, call it and do nothing else.
        if (codeScanningData.action) {
            return await codeScanningData.action();
        }
        // Depending of the configuration, the user can be forced to scan a specific QRcode type.
        const check = this._checkBarcode(codeScanningData);
        if (check.error) {
            return this.notification(check.message, { title: check.title, type: "danger" });
        }

        if (codeScanningData.packaging) {
            codeScanningData.product = this.cache.getRecord('product.product', codeScanningData.packaging.product_id);
            codeScanningData.quantity = ('quantity' in codeScanningData ? codeScanningData.quantity : 1) * codeScanningData.packaging.qty;
            codeScanningData.uom = this.cache.getRecord('uom.uom', codeScanningData.product.uom_id);
        }

        // Remembers the product if a (packaging) product was scanned.
        if (codeScanningData.product) {
            this.lastScanned.product = codeScanningData.product;
        }

        if (codeScanningData.lot && !codeScanningData.product) {
            codeScanningData.product = this.cache.getRecord('product.product', codeScanningData.lot.product_id);
        }

        await this._processLocation(codeScanningData);
        await this._processPackage(codeScanningData);
        if (codeScanningData.stopped) {
            // TODO: Sometime we want to stop here instead of keeping doing thing,
            // but it's a little hacky, it could be better to don't have to do that.
            return;
        }

        if (codeScanningData.weight) { // Convert the weight into quantity.
            codeScanningData.quantity = codeScanningData.weight.value;
        }

        // If no product found, take the one from last scanned line if possible.
        if (!codeScanningData.product) {
            if (operation_type == 'incoming') {
                currentLine = this._findLineByQRCode(codeScanning);
                debugger
            } else if (operation_type == 'outgoing') {
                if (codeScanningData.quantity) {
                    currentLine = this.selectedLine || this.lastScannedLine;
                } else if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
                    currentLine = this.selectedLine;
                } else if (this.lastScannedLine && this.lastScannedLine.product_id.tracking !== 'none') {
                    currentLine = this.lastScannedLine;
                }
                if (!currentLine) {
                    return this.notification(
                        _t("The scanned code does not exist in the delivery note, please check again!"),
                        { title: "Not found", type: "danger" }
                    );
                }
            }
            if (currentLine) { // If we can, get the product from the previous line.
                const previousProduct = currentLine.product_id;
                // If the current product is tracked and the QRcode doesn't fit
                // anything else, we assume it's a new lot/serial number.
                if (previousProduct.tracking !== 'none' && !codeScanningData.match && this.canCreateNewLot) {
                    this.trigger('flash');
                    codeScanningData.lotName = codeScanning;
                    codeScanningData.product = previousProduct;
                }
                if (codeScanningData.lot || codeScanningData.lotName ||
                    codeScanningData.quantity) {
                    codeScanningData.product = previousProduct;
                }
            }
        }
        const { product } = codeScanningData;
        if (!product && codeScanningData.match && this.parser.nomenclature.is_gs1_nomenclature) {
            // Special case where something was found using the GS1 nomenclature but no product is
            // used (eg.: a product's barcode can be read as a lot is starting with 21).
            // In such case, tries to find a record with the barcode by by-passing the parser.
            codeScanningData = await this._fetchRecordFromTheCache(barcode, filters);
            if (codeScanningData.packaging) {
                Object.assign(codeScanningData, this._retrievePackagingData(codeScanningData));
            } else if (codeScanningData.lot) {
                Object.assign(codeScanningData, this._retrieveTrackingNumberInfo(codeScanningData.lot));
            }
            if (codeScanningData.product) {
                product = codeScanningData.product;
            } else if (codeScanningData.match) {
                await this._processPackage(codeScanningData);
                if (codeScanningData.stopped) {
                    return;
                }
            }
        }
        if (!product) { // Product is mandatory, if no product, raises a warning.
            if (!codeScanningData.error) {
                if (this.groups.group_tracking_lot) {
                    codeScanningData.error = _t("You are expected to scan one or more products or a package available at the picking location");
                } else {
                    codeScanningData.error = _t("You are expected to scan one or more products.");
                }
            }
            return this.notification(codeScanningData.error, { type: "danger" });
        } else if (codeScanningData.lot && codeScanningData.lot.product_id !== product.id) {
            delete codeScanningData.lot; // The product was scanned alongside another product's lot.
        }
        if (codeScanningData.weight) { // the encoded weight is based on the product's UoM
            codeScanningData.uom = this.cache.getRecord('uom.uom', product.uom_id);
        }

        // Searches and selects a line if needed.
        if (!currentLine || this._shouldSearchForAnotherLine(currentLine, codeScanningData)) {

            if (currentLine && operation_type == 'incoming') {
                console.log("pass")
            } else {
                currentLine = this._findLine(codeScanningData);
            }

        }

        // Default quantity set to 1 by default if the product is untracked or
        // if there is a scanned tracking number.
        if (product.tracking === 'none' || codeScanningData.lot || codeScanningData.lotName || this._incrementTrackedLine()) {
            const hasUnassignedQty = currentLine && currentLine.qty_done && !currentLine.lot_id && !currentLine.lot_name;
            const isTrackingNumber = codeScanningData.lot || codeScanningData.lotName;
            const defaultQuantity = isTrackingNumber && hasUnassignedQty ? 0 : 1;
            codeScanningData.quantity = codeScanningData.quantity || defaultQuantity;
            if (product.tracking === 'serial' && codeScanningData.quantity > 1 && (codeScanningData.lot || codeScanningData.lotName)) {
                codeScanningData.quantity = 1;
                this.notification(
                    _t(`A product tracked by serial numbers can't have multiple quantities for the same serial number.`),
                    { type: 'danger' }
                );
            }
        }

        if ((codeScanningData.lotName || codeScanningData.lot) && product) {
            const lotName = codeScanningData.lotName || codeScanningData.lot.name;
            for (const line of this.currentState.lines) {
                if (line.product_id.tracking === 'serial' && this.getQtyDone(line) !== 0 &&
                    ((line.lot_id && line.lot_id.name) || line.lot_name) === lotName) {
                    return this.notification(
                        _t("The scanned Serial Code number is already used."),
                        { type: 'danger' }
                    );
                }
            }
            // Prefills `owner_id` and `package_id` if possible.
            const prefilledOwner = (!currentLine || (currentLine && !currentLine.owner_id)) && this.groups.group_tracking_owner && !codeScanningData.owner;
            const prefilledPackage = (!currentLine || (currentLine && !currentLine.package_id)) && this.groups.group_tracking_lot && !codeScanningData.package;
            if (this.useExistingLots && (prefilledOwner || prefilledPackage)) {
                const lotId = (codeScanningData.lot && codeScanningData.lot.id) || (currentLine && currentLine.lot_id && currentLine.lot_id.id) || false;
                const res = await this.orm.call(
                    'product.product',
                    'prefilled_owner_package_stock_barcode',
                    [product.id],
                    {
                        lot_id: lotId,
                        lot_name: (!lotId && codeScanningData.lotName) || false,
                    }
                );
                this.cache.setCache(res.records);
                if (prefilledPackage && res.quant && res.quant.package_id) {
                    codeScanningData.package = this.cache.getRecord('stock.quant.package', res.quant.package_id);
                }
                if (prefilledOwner && res.quant && res.quant.owner_id) {
                    codeScanningData.owner = this.cache.getRecord('res.partner', res.quant.owner_id);
                }
            }
        }

        // Updates or creates a line based on barcode data.
        if (currentLine) { // If line found, can it be incremented ?
            if (operation_type == 'incoming') {
                var params = {
                    line: currentLine,
                    codeScanningData: codeScanningData,
                    remainingLines: this._findRemainingLines(currentLine),
                }
                debugger

                this.dialogService.add(ScanLotSerial, {
                    title: _t("Scan serial numbers"),
                    body: _t(""),
                    context: params,
                    confirm: async (data) => {
                        codeScanningData = data['codeScanningData']
                        let exceedingQuantity = 0;

                        if (product.tracking !== 'serial' && codeScanningData.uom && codeScanningData.uom.category_id == currentLine.product_uom_id.category_id) {
                            // convert to current line's uom
                            codeScanningData.quantity = (codeScanningData.quantity / codeScanningData.uom.factor) * currentLine.product_uom_id.factor;
                            codeScanningData.uom = currentLine.product_uom_id;
                        }
                        // Checks the quantity doesn't exceed the line's remaining quantity.
                        if (currentLine.reserved_uom_qty && product.tracking === 'none') {
                            const remainingQty = currentLine.reserved_uom_qty - currentLine.qty_done;
                            if (codeScanningData.quantity > remainingQty && this._shouldCreateLineOnExceed(currentLine)) {
                                // In this case, lowers the increment quantity and keeps
                                // the excess quantity to create a new line.
                                exceedingQuantity = codeScanningData.quantity - remainingQty;
                                codeScanningData.quantity = remainingQty;
                            }
                        }
                        if (codeScanningData.quantity > 0 || codeScanningData.lot || codeScanningData.lotName) {
                            const fieldsParams = this._convertDataToFieldsParams(QRcodeData);
                            if (codeScanningData.uom) {
                                fieldsParams.uom = codeScanningData.uom;
                            }
                            await this.updateLine(currentLine, fieldsParams);
                        }
                        if (exceedingQuantity) { // Creates a new line for the excess quantity.
                            codeScanningData.quantity = exceedingQuantity;
                            const fieldsParams = this._convertDataToFieldsParams(QRcodeData);

                            if (codeScanningData.uom) {
                                fieldsParams.uom = codeScanningData.uom;
                            }
                            currentLine = await this._createNewLine({
                                copyOf: currentLine,
                                fieldsParams,
                            });
                        }

                        if (currentLine) {
                            this._selectLine(currentLine);
                        }
                        this.trigger('update');
                    },
                })
            } else {
                let exceedingQuantity = 0;
                if (product.tracking !== 'serial' && codeScanningData.uom && codeScanningData.uom.category_id == currentLine.product_uom_id.category_id) {
                    // convert to current line's uom
                    codeScanningData.quantity = (codeScanningData.quantity / codeScanningData.uom.factor) * currentLine.product_uom_id.factor;
                    codeScanningData.uom = currentLine.product_uom_id;
                }
                // Checks the quantity doesn't exceed the line's remaining quantity.
                if (currentLine.reserved_uom_qty && product.tracking === 'none') {
                    const remainingQty = currentLine.reserved_uom_qty - currentLine.qty_done;

                    if (codeScanningData.quantity > remainingQty && this._shouldCreateLineOnExceed(currentLine)) {
                        // In this case, lowers the increment quantity and keeps
                        // the excess quantity to create a new line.
                        exceedingQuantity = codeScanningData.quantity - remainingQty;
                        codeScanningData.quantity = remainingQty;
                    }
                }
                if (codeScanningData.quantity > 0 || codeScanningData.lot || codeScanningData.lotName) {
                    const fieldsParams = this._convertDataToFieldsParams(codeScanningData);
                    if (codeScanningData.uom) {
                        fieldsParams.uom = codeScanningData.uom;
                    }
                    await this.updateLine(currentLine, fieldsParams);
                }
                if (exceedingQuantity) { // Creates a new line for the excess quantity.
                    codeScanningData.quantity = exceedingQuantity;
                    const fieldsParams = this._convertDataToFieldsParams(codeScanningData);

                    if (codeScanningData.uom) {
                        fieldsParams.uom = codeScanningData.uom;
                    }
                    currentLine = await this._createNewLine({
                        copyOf: currentLine,
                        fieldsParams,
                    });
                }
            }
        } else {
            this.notification(
                _t("The serial number code doesn't exists in list."),
                { type: "warning" }
            );
        }

        // And finally, if the scanned barcode modified a line, selects this line.
        if (currentLine) {
            this._selectLine(currentLine);
        }
        this.trigger('update');
    },

    /**
     * Starts by parse the QR-Code and then process each type of QR-Code data.
     *
     * @param {string} code
     * @returns {Promise}
     */

    async _processQRCode(code, moveLineObj) {
        let QRcodeData = moveLineObj[0] || {};
        let serialNumberCode = QRcodeData.lot_name || '';
        let weekNumber = QRcodeData.inventory_period_name || '';
        let currentLine = false;

        if (code.length < 4) {
            return this.notification(
                _t("Invalid QR code, please try again!"),
                { type: "danger" }
            );
        }

        if (weekNumber && code.slice(0, 4) != weekNumber) {
            return this.notification(
                _t("The scanned code with Weeknumber is not in the current delivery note, please check again!"),
                { type: "danger" }
            );
        }

        const filters = {};
        if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
            filters['stock.lot'] = {
                product_id: this.selectedLine.product_id.id,
            };
        }
        try {
            QRcodeData = await this._parseBarcode(serialNumberCode, filters);
            if (this._shouldSearchForAnotherLot(QRcodeData, filters)) {
                // Retry to parse the barcode without filters in case it matches an existing
                // record that can't be found because of the filters
                const lot = await this.cache.getRecordByBarcode(serialNumberCode, 'stock.lot');
                if (lot) {
                    Object.assign(QRcodeData, { lot, match: true });
                }
            }
        } catch (parseErrorMessage) {
            QRcodeData.error = parseErrorMessage;
        }

        // [Update] QR-Code & Week Number in QRcodeData
        QRcodeData['qrcode'] = code;
        QRcodeData['inventory_period_name'] = weekNumber;

        // Keep in memory every scans.
        this.scanHistory.unshift(QRcodeData);

        if (QRcodeData.match) { // Makes flash the screen if the scanned barcode was recognized.
            this.trigger('flash');
        }

        // Depending of the configuration, the user can be forced to scan a specific barcode type.
        const check = this._checkBarcode(QRcodeData);
        if (check.error) {
            return this.notification(check.message, { title: check.title, type: "danger" });
        }

        if (QRcodeData.packaging) {
            QRcodeData.product = this.cache.getRecord('product.product', QRcodeData.packaging.product_id);
            QRcodeData.quantity = ("quantity" in barcodeData ? QRcodeData.quantity : 1) * barcodeData.packaging.qty;
            QRcodeData.uom = this.cache.getRecord('uom.uom', QRcodeData.product.uom_id);
        }

        if (QRcodeData.product) { // Remembers the product if a (packaging) product was scanned.
            this.lastScanned.product = QRcodeData.product;
        }

        if (QRcodeData.lot && !QRcodeData.product) {
            QRcodeData.product = this.cache.getRecord('product.product', QRcodeData.lot.product_id);
        }

        await this._processLocation(QRcodeData);
        await this._processPackage(QRcodeData);
        if (QRcodeData.stopped) {
            // TODO: Sometime we want to stop here instead of keeping doing thing,
            // but it's a little hacky, it could be better to don't have to do that.
            return;
        }

        if (QRcodeData.weight) { // Convert the weight into quantity.
            QRcodeData.quantity = QRcodeData.weight.value;
        }

        // If no product found, take the one from last scanned line if possible.
        if (!QRcodeData.product) {
            if (QRcodeData.quantity) {
                currentLine = this.selectedLine || this.lastScannedLine;
            } else if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
                currentLine = this.selectedLine;
            } else if (this.lastScannedLine && this.lastScannedLine.product_id.tracking !== 'none') {
                currentLine = this.lastScannedLine;
            }
            if (currentLine) { // If we can, get the product from the previous line.
                const previousProduct = currentLine.product_id;
                // If the current product is tracked and the barcode doesn't fit
                // anything else, we assume it's a new lot/serial number.
                if (previousProduct.tracking !== 'none' &&
                    !QRcodeData.match && this.canCreateNewLot) {
                    this.trigger('flash');
                    QRcodeData.lotName = barcode;
                    QRcodeData.product = previousProduct;
                }
                if (QRcodeData.lot || QRcodeData.lotName ||
                    QRcodeData.quantity) {
                    QRcodeData.product = previousProduct;
                }
            }
        }

        const { product } = QRcodeData;
        if (!product) { // Product is mandatory, if no product, raises a warning.
            if (!QRcodeData.error) {
                if (this.groups.group_tracking_lot) {
                    QRcodeData.error = _t("You are expected to scan one or more products or a package available at the picking location");
                } else {
                    QRcodeData.error = _t("You are expected to scan one or more products.");
                }
            }
            return this.notification(QRcodeData.error, { type: "danger" });
        } else if (QRcodeData.lot && QRcodeData.lot.product_id !== product.id) {
            delete QRcodeData.lot; // The product was scanned alongside another product's lot.
        }
        if (QRcodeData.weight) { // the encoded weight is based on the product's UoM
            QRcodeData.uom = this.cache.getRecord('uom.uom', product.uom_id);
        }

        // Searches and selects a line if needed.
        if (!currentLine || this._shouldSearchForAnotherLine(currentLine, QRcodeData)) {
            currentLine = this._findLine(QRcodeData);
        }

        // Default quantity set to 1 by default if the product is untracked or
        // if there is a scanned tracking number.
        if (product.tracking === 'none' || QRcodeData.lot || QRcodeData.lotName || this._incrementTrackedLine()) {
            const hasUnassignedQty = currentLine && currentLine.qty_done && !currentLine.lot_id && !currentLine.lot_name;
            const isTrackingNumber = QRcodeData.lot || QRcodeData.lotName;
            const defaultQuantity = isTrackingNumber && hasUnassignedQty ? 0 : 1;
            QRcodeData.quantity = QRcodeData.quantity || defaultQuantity;
            if (product.tracking === 'serial' && QRcodeData.quantity > 1 && (QRcodeData.lot || QRcodeData.lotName)) {
                QRcodeData.quantity = 1;
                this.notification(
                    _t(`A product tracked by serial numbers can't have multiple quantities for the same serial number.`),
                    { type: 'danger' }
                );
            }
        }

        if ((QRcodeData.lotName || QRcodeData.lot) && product) {
            const lotName = QRcodeData.lotName || QRcodeData.lot.name;
            for (const line of this.currentState.lines) {
                if (line.product_id.tracking === 'serial' && this.getQtyDone(line) !== 0 &&
                    ((line.lot_id && line.lot_id.name) || line.lot_name) === lotName) {
                    return this.notification(
                        _t("The scanned QR-Code number is already used."),
                        { type: 'danger' }
                    );
                }
            }
            // Prefills `owner_id` and `package_id` if possible.
            const prefilledOwner = (!currentLine || (currentLine && !currentLine.owner_id)) && this.groups.group_tracking_owner && !QRcodeData.owner;
            const prefilledPackage = (!currentLine || (currentLine && !currentLine.package_id)) && this.groups.group_tracking_lot && !QRcodeData.package;
            if (this.useExistingLots && (prefilledOwner || prefilledPackage)) {
                const lotId = (QRcodeData.lot && QRcodeData.lot.id) || (currentLine && currentLine.lot_id && currentLine.lot_id.id) || false;
                const res = await this.orm.call(
                    'product.product',
                    'prefilled_owner_package_stock_barcode',
                    [product.id],
                    {
                        lot_id: lotId,
                        lot_name: (!lotId && QRcodeData.lotName) || false,
                    }
                );
                this.cache.setCache(res.records);
                if (prefilledPackage && res.quant && res.quant.package_id) {
                    QRcodeData.package = this.cache.getRecord('stock.quant.package', res.quant.package_id);
                }
                if (prefilledOwner && res.quant && res.quant.owner_id) {
                    QRcodeData.owner = this.cache.getRecord('res.partner', res.quant.owner_id);
                }
            }
        }

        // Updates or creates a line based on qr-code data.
        if (currentLine && currentLine.qr_code == QRcodeData.qrcode) { // If line found, can it be incremented ?
            let exceedingQuantity = 0;
            if (product.tracking !== 'serial' && QRcodeData.uom && QRcodeData.uom.category_id == currentLine.product_uom_id.category_id) {
                // convert to current line's uom
                QRcodeData.quantity = (QRcodeData.quantity / QRcodeData.uom.factor) * currentLine.product_uom_id.factor;
                QRcodeData.uom = currentLine.product_uom_id;
            }
            // Checks the quantity doesn't exceed the line's remaining quantity.
            if (currentLine.reserved_uom_qty && product.tracking === 'none') {
                const remainingQty = currentLine.reserved_uom_qty - currentLine.qty_done;
                if (QRcodeData.quantity > remainingQty && this._shouldCreateLineOnExceed(currentLine)) {
                    // In this case, lowers the increment quantity and keeps
                    // the excess quantity to create a new line.
                    exceedingQuantity = QRcodeData.quantity - remainingQty;
                    QRcodeData.quantity = remainingQty;
                }
            }
            if (QRcodeData.quantity > 0 || QRcodeData.lot || QRcodeData.lotName) {
                const fieldsParams = this._convertDataToFieldsParams(QRcodeData);
                if (QRcodeData.uom) {
                    fieldsParams.uom = QRcodeData.uom;
                }
                await this.updateLine(currentLine, fieldsParams);
            }
            if (exceedingQuantity) { // Creates a new line for the excess quantity.
                QRcodeData.quantity = exceedingQuantity;
                const fieldsParams = this._convertDataToFieldsParams(QRcodeData);
                if (QRcodeData.uom) {
                    fieldsParams.uom = QRcodeData.uom;
                }
                currentLine = await this._createNewLine({
                    copyOf: currentLine,
                    fieldsParams,
                });
            }

            if (currentLine) {
                this._selectLine(currentLine);
            }
            this.trigger('update');

        } else if (currentLine && currentLine.qr_code != QRcodeData.qrcode) {

            let allScanedQRCode = currentLine.all_scaned_qrcode
            let lot_serial_qrcode = currentLine.lot_serial_qrcode

            if (allScanedQRCode && allScanedQRCode.includes(QRcodeData.qrcode)) {
                return this.notification(
                    _t("The scanned QR-Code already exists in the done picking, please check again !!!"),
                    { type: "danger" }
                );
            } else if (lot_serial_qrcode && !lot_serial_qrcode[QRcodeData.qrcode]) {
                return this.notification(
                    _t("The scanned QR-Code does not exist in the product Lot/Serial, please check again !!!"),
                    { type: "danger" }
                );
            }

            const lot = lot_serial_qrcode[QRcodeData.qrcode]
            QRcodeData.lot = lot
            QRcodeData.quantity = 1

            const fieldsParams = this._convertDataToFieldsParams(QRcodeData);

            currentLine.qr_code = QRcodeData.qrcode
            currentLine.qty_done = 0

            await this.updateLine(currentLine, fieldsParams);

            if (currentLine) {
                this._selectLine(currentLine);
            }
            this.trigger('update');
        } else {
            this.notification(
                _t("The QR-Code number doesn't exists in list."),
                { type: "warning" }
            );
        }

        // And finally, if the scanned qr-code modified a line, selects this line.
        if (currentLine) {
            this._selectLine(currentLine);
        }
        this.trigger('update');
    },

    async _parseQRCode(code, filters) {
        const result = {
            code,
            match: false,
        };
        const recordByData = await this.getRecordByQRCode(code, false, false, filters);
        if (this.useExistingMoveLines) {
            const moveLine = recordByData.get('stock.move.line');
            if (moveLine) {
                result.moveLine = moveLine;
                result.match = true;
            }
        }

        return result;
    },

    async getRecordByQRCode(code, model = false, onlyInCache = false, filters = {}) {
        if (model) {
            if (!this.dbBarcodeCache.hasOwnProperty(model)) {
                throw new Error(`Model ${model} doesn't exist in the cache`);
            }
            if (!this.dbBarcodeCache[model].hasOwnProperty(code)) {
                if (onlyInCache) {
                    return null;
                }
                await this._getMissingRecord(code, model, filters);
                return await this.getRecordByQRCode(code, model, true, filters);
            }
            const ids = this.dbBarcodeCache[model][code];
            for (const id of ids) {
                const record = this.getRecord(model, id);
                let pass = true;
                if (filters[model]) {
                    const fields = Object.keys(filters[model]);
                    for (const field of fields) {
                        if (record[field] != filters[model][field]) {
                            pass = false;
                            break;
                        }
                    }
                }
                if (pass) {
                    return record;
                }
            }
        } else {
            const result = new Map();
            // Returns object {model: record} of possible record.
            const models = Object.keys(this.dbBarcodeCache);
            for (const model of models) {
                if (this.dbBarcodeCache[model].hasOwnProperty(code)) {
                    const ids = this.dbBarcodeCache[model][code];
                    for (const id of ids) {
                        const record = this.dbIdCache[model][id];
                        let pass = true;
                        if (filters[model]) {
                            const fields = Object.keys(filters[model]);
                            for (const field of fields) {
                                if (record[field] != filters[model][field]) {
                                    pass = false;
                                    break;
                                }
                            }
                        }
                        if (pass) {
                            result.set(model, JSON.parse(JSON.stringify(record)));
                            break;
                        }
                    }
                }
            }
            if (result.size < 1) {
                if (onlyInCache) {
                    return result;
                }
                await this._getMissingRecord(code, model, filters);
                return await this.getRecordByQRCode(code, model, true, filters);
            }
            return result;
        }
    },

    _shouldSearchForAnotherMoveLine(code, filters) {
        return !code.match && filters['stock.move.line'] && this.useExistingMoveLines;
    },

    checkQRCode(scannedCode) {
        if (this.record.all_barcode.includes(scannedCode)) {
            return true;
        }
        return false;
    },

});
