/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";


patch(BarcodePickingModel.prototype, {
    /**
     * @override by MOVEOPLUS
     * Validation cannot OVER on product demand
     * INHERIT Function: '_processBarcode' => To handle new workflow of barcode for qr-code
     */

    setData(data) {
        super.setData(...arguments);
        super.setData(data);
        this.reset_scanning_qrcode();
    },

    // ACTIONS

    reset_scanning_qrcode() {
        this.QRProduct = false;
        this.QRcodeData = {};
        this.QRCodeLineScanning = {};
        // ValidateData
        this.validateQRCode = false;
    },

    // --------------------------------------------------------------------------
    // Private
    // --------------------------------------------------------------------------

    async _processBarcode(barcode) {
        const codeScanning = barcode;
        const operationType = this.config.operation_type;

        if (operationType && ["incoming", "outgoing"].includes(operationType)) {
            console.debug("- Picking Type: " + operationType);
            console.debug("- Code Scanning: " + codeScanning);

            if (operationType === "outgoing") {
                return this._processCode(codeScanning, operationType);
            } else {
                const codeExist = this.checkQRCodeExistsInReceipt(codeScanning);
                if (!codeExist) {
                    const exitsNotQRCode = this.checkBarcodeExitsInReceipt(codeScanning);
                    if (!exitsNotQRCode) {
                        return this.notification(_t("QR Code/Line Code is not in the receipt list."), { type: "warning" });
                    }
                }
                return super._processBarcode(codeScanning);
            }
        }

        return super._processBarcode(codeScanning);
    },


    async _processQRCodeCurrentLineOutgoing(qr_code) {
        if (qr_code.length < 4) {
            return this.notification(_t("Invalid QR code, please check again!"), { type: "danger" });
        } else {
            var weekNumber = this.QRCodeLineScanning.inventory_period_name
            var QRcodeData = this.QRcodeData
            var currentLine = this.QRCodeLineScanning
            var product = this.QRProduct

            if (qr_code.slice(0, 4) != weekNumber) {
                return this.notification(_t("QR code with Weeknumber is not in the current delivery note!!!"), { type: "danger" });
            } else if (this.QRCodeLineScanning.qr_code == qr_code) {
                QRcodeData.quantity = 1
                let exceedingQuantity = 0;
                let exceedingQuantityQR = 0

                if (product.tracking !== 'serial' && QRcodeData.uom && QRcodeData.uom.category_id == currentLine.product_uom_id.category_id) {
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
                    exceedingQuantityQR = fieldsParams.qty_done + currentLine.qty_done

                    if (exceedingQuantityQR > currentLine.quantity) {
                        return this.notification(_t("The number on the line is complete, please scan another line!!!!"), { type: "danger" });
                    }

                    await this.updateLine(currentLine, fieldsParams);
                }

                // [CREATE] Create a new line for the excess quantity
                if (exceedingQuantity) {
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
            } else if (this.QRCodeLineScanning.qr_code != qr_code) {
                var all_scaned_qrcode = currentLine.all_scaned_qrcode
                var lot_serial_qrcode = currentLine.lot_serial_qrcode

                if (all_scaned_qrcode && all_scaned_qrcode.includes(qr_code)) {
                    return this.notification(_t("The scanned QrCode already exists in the done picking, please check again !!!"), { type: "danger" });
                } else if (lot_serial_qrcode && !lot_serial_qrcode[qr_code]) {
                    return this.notification(_t("The scanned QrCode does not exist in the product Lot/Serial, please check again !!!"), { type: "danger" });
                }

                const lot = lot_serial_qrcode[qr_code]
                QRcodeData.lot = lot
                QRcodeData.quantity = 1

                const fieldsParams = this._convertDataToFieldsParams(QRcodeData);

                currentLine.qr_code = qr_code
                currentLine.qty_done = 0

                await this.updateLine(currentLine, fieldsParams);

                if (currentLine) {
                    this._selectLine(currentLine);
                }
                this.trigger('update');
            }
        }
        return;
    },

    async _processCode(codeScanning, operation_type = "incoming") {

        if (this.isDone && !this.commands[codeScanning]) {
            return this.notification(_t("Picking is already DONE!"), { type: "danger" });
        }

        // QR-Code workflow
        if (this.validateQRCode && operation_type == "outgoing") {
            let checkCodeScanning = this.checkQRCode(codeScanning);
            if (!checkCodeScanning) {
                return this._processQRCodeCurrentLineOutgoing(codeScanning);
            }
        }

        let codeScanningData = {};
        let currentLine = false;
        // Creates a filter if needed, which can help to get the right record
        // when multiple records have the same model and QR Code/Line Code.
        const filters = {};
        const moveLineFilters = {};
        if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
            filters['stock.lot'] = {
                product_id: this.selectedLine.product_id.id,
            };
            moveLineFilters['stock.move.line'] = {
                product_id: this.selectedLine.product_id.id,
                qr_code: this.selectedLine.qr_code,
                weekNumber: this.selectedLine.inventory_period_name,
            };
        }
        try {
            codeScanningData = await this._parseBarcode(codeScanning, filters);
            if (this._shouldSearchForAnotherLot(codeScanningData, filters)) {
                const lot = await this.cache.getRecordByBarcode(codeScanning, 'stock.lot');
                if (lot) {
                    Object.assign(codeScanningData, { lot, match: true });
                }
            }
        } catch (parseErrorMessage) {
            codeScanningData.error = parseErrorMessage;
        }

        console.debug("===== QR-Code Data: " + JSON.stringify(codeScanningData));

        // Keep in memory every scans.
        this.scanHistory.unshift(codeScanningData);

        if (codeScanningData.match) { // Makes flash the screen if the scanned QRcode was recognized.
            this.trigger('flash');
        }

        // Process each data in order, starting with non-ambiguous data type.
        if (codeScanningData.action) { // As action is always a single data, call it and do nothing else.
            return await codeScanningData.action();
        }
        // Depending of the configuration, the user can be forced to scan a specific QRcode type.
        const check = this._checkBarcode(codeScanningData);
        if (check.error) {
            return this.notification(check.message, { title: check.title, type: "danger" });
        }

        if (codeScanningData.packaging) {
            // Object.assign(codeScanningData, this._retrievePackagingData(codeScanningData));
            codeScanningData.product = this.cache.getRecord('product.product', codeScanningData.packaging.product_id);
            codeScanningData.quantity = ("quantity" in codeScanningData ? codeScanningData.quantity : 1) * codeScanningData.packaging.qty;
            codeScanningData.uom = this.cache.getRecord('uom.uom', codeScanningData.product.uom_id);
        }

        if (codeScanningData.product) { // Remembers the product if a (packaging) product was scanned.
            this.lastScanned.product = codeScanningData.product;
        }

        if (codeScanningData.lot && !codeScanningData.product) {
            // Object.assign(codeScanningData, this._retrieveTrackingNumberInfo(codeScanningData.lot));
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
        // 

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
                    return this.notification(_t("The scanned code does not exist in the delivery note, please check again!"),
                        { title: "Not found", type: "danger" }
                    );
                }
            }
            if (currentLine) { // If we can, get the product from the previous line.
                const previousProduct = currentLine.product_id;
                // If the current product is tracked and the QRcode doesn't fit
                // anything else, we assume it's a new lot/serial number.
                if (previousProduct.tracking !== 'none' &&
                    !codeScanningData.match && this.canCreateNewLot) {
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
                        _t("The scanned serial number is already used."),
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
                if (currentLine.inventory_period_id) {
                    if (codeScanningData) {
                        var msg = _t("Start scanning the QR CODE for product ") + "'" + currentLine.product_id.display_name + "'"
                        this.notification(msg,
                            { title: "*** QRCODE ***", type: "success" }
                        );
                        this.validateQRCode = true
                        this.QRCodeLineScanning = currentLine
                        this.codeScanningData = codeScanningData
                        this.QRProduct = product
                    }

                } else {
                    if (codeScanningData) {
                        this.reset_scanning_qrcode()
                        var msg = _t("Scanning is scanning with product ") + "'[" + currentLine.product_id.display_name + "]'"
                        this.notification(msg,
                            { title: "NOT QRCODE", type: "success" }
                        );
                    }

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
            }
        } else { // No line found, so creates a new one.
            console.log("pass......")
        }

        if (currentLine) {
            this._selectLine(currentLine);
        }
        this.trigger('update');
    },

    checkQRCode(scannedCode) {
        if (this.record.all_barcode.includes(scannedCode)) {
            return true;
        }
        return false;
    },

});
