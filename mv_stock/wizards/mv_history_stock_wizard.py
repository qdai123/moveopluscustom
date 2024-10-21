from odoo import models, fields, api, _


class MVHistoryStockWizard(models.TransientModel):
    _name = "mv.history.stock.wizard"
    _description = _("Wizard: MV History Stock")

    date_from = fields.Datetime("Từ ngày", required=True)
    date_to = fields.Datetime("Đến ngày", required=True)

    def export_stock(self):
        self.ensure_one()

        product_domain = [("detailed_type", "=", "product")]
        if not self.user_has_groups("stock.group_stock_manager"):
            products_in_warehouse = self.env["stock.move.line"].search_read(
                domain=[
                    ("location_id.warehouse_id.allow_stock_users_access", "=", True),
                    (
                        "location_id.warehouse_id.stock_users_access_ids",
                        "in",
                        [self.env.user.id],
                    ),
                ],
                fields=["product_id"],
            )
            products_in_warehouse = list(
                set([product["product_id"][0] for product in products_in_warehouse])
            )
            product_domain.append(
                (
                    "id",
                    "in",
                    [product_id for product_id in products_in_warehouse],
                )
            )

        products = self.env["product.product"].search(product_domain)

        self.env["mv.history.stock"].search(
            [("create_uid", "=", self.env.user.id)]
        ).unlink()
        history_stocks = self.env["mv.history.stock"]
        sequence = 1
        for product in products:
            stock = self.env["mv.history.stock"].create(
                {
                    "product_id": product.id,
                    "date_from": self.date_from,
                    "report_date_from": self.date_from.date().strftime("%d/%m/%Y"),
                    "date_to": self.date_to,
                    "report_date_to": self.date_to.date().strftime("%d/%m/%Y"),
                    "sequence": sequence,
                }
            )
            sequence += 1
            history_stocks |= stock
        return {
            "type": "ir.actions.act_window",
            "name": _("Xuất/Nhập tồn"),
            "res_model": "mv.history.stock",
            "view_mode": "tree",
            "views": [(self.env.ref("mv_stock.mv_history_stock_view_tree").id, "tree")],
            "domain": [("id", "in", history_stocks.ids)],
            "context": {},
            "target": "current",
        }
