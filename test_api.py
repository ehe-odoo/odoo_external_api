# This script uses python 3 version of Odoo external API documentation
# Official documentation (which supports python 2) can be found at:
# https://www.odoo.com/documentation/11.0/webservices/odoo.html

import sys, logging

# in python 2, it was `import xmlrpclib`
from xmlrpc import client

URL = "http://127.0.0.1:8069"
DB = "contec_test2"
USER = "odooimporttest@odoo.test.com"
PW = "importpasswordmustbelongotherwiseitisnotsafe"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",
)


def login_and_verify_access(url, db, username, password, target_models):
    # Logging in
    common = client.ServerProxy("{}/xmlrpc/2/common".format(url))
    # print(common.version())
    uid = common.authenticate(db, username, password, {})
    # getting models
    models = client.ServerProxy("{}/xmlrpc/2/object".format(url))

    for t_model in target_models:
        can_read_model = models.execute_kw(
            db,
            uid,
            password,
            t_model,
            "check_access_rights",
            ["write"],
            {"raise_exception": False},
        )
        if not can_read_model:
            logging.error(
                "User {} do not have access right to {} model".format(username, t_model)
            )
            sys.exit()

    return uid, models


def run():
    url, db, username, password = URL, DB, USER, PW
    target_models = [
        "product.template",
        "res.partner",
        "sale.order",
        "sale.order.line",
        "account.invoice",
        "account.invoice.line",
        "stock.picking",
        "stock.inventory",
    ]
    uid, models = login_and_verify_access(url, db, username, password, target_models)

    product_template_name = "Test Storable Product"
    logging.info(
        "Searching for product [{}] in current database...".format(
            product_template_name
        )
    )
    product_template_id = models.execute_kw(
        db,
        uid,
        password,
        "product.template",
        "search",
        [[("name", "=", product_template_name)]],
    )

    if not product_template_id:
        # create a test product
        logging.info("Test Product not found, creating one now...")

        product_template_id = models.execute_kw(
            db,
            uid,
            password,
            "product.template",
            "create",
            [
                {
                    "name": product_template_name,
                    "sale_ok": True,
                    "purchase_ok": True,
                    "default_code": "TESTSTORABLE",
                    "type": "product",
                    "standard_price": 1.00,
                    "list_price": 2.00,
                    "uom_id": 1,
                }
            ],
        )
    else:
        product_template_id = product_template_id[0]

    # In SOL, INVL, DOL, we uses product.product of the product.template,
    # Please notice they are two different objects
    product_id = models.execute_kw(
        db,
        uid,
        password,
        "product.product",
        "search",
        [[("product_tmpl_id", "=", product_template_id)]],
    )[0]

    customer_name = "Test Customer"
    logging.info(
        "Searching for customer [{}] in current database...".format(customer_name)
    )
    partner_id = models.execute_kw(
        db, uid, password, "res.partner", "search", [[("name", "=", customer_name)]]
    )

    if not partner_id:
        logging.info("Test Customer not found, creating one now...")
        partner_id = models.execute_kw(
            db,
            uid,
            password,
            "res.partner",
            "create",
            [{"name": customer_name, "company_type": "company"}],
        )
    else:
        partner_id = partner_id[0]

    # create a sale order
    logging.info("Creating Sale Order for Test Customer...")
    sale_order_id = models.execute_kw(
        db, uid, password, "sale.order", "create", [{"partner_id": partner_id}]
    )

    # add an so line, you can also add SOL inside of an SO during creation
    # see later demo on how relational fields can be created on the fly
    logging.info("Adding one sale order line with Test Product...")
    sale_order_line_id = models.execute_kw(
        db,
        uid,
        password,
        "sale.order.line",
        "create",
        [{"order_id": sale_order_id, "product_id": product_id}],
    )

    # confirm this order
    logging.info(
        "Confirming Sale Order... (Delivery Order will be created automatically when a Sale Order is confirmed.)"
    )
    models.execute_kw(
        db, uid, password, "sale.order", "action_confirm", [sale_order_id]
    )

    # create invoice, most simple example
    logging.info("Creating Invoice for this Sale Order...")
    models.execute_kw(
        db, uid, password, "sale.order", "action_invoice_create", [sale_order_id]
    )

    # read all invoices related to this sale order
    logging.info("Finding invoices that are created from this Sale Order...")
    read_sale_order_fields = models.execute_kw(
        db,
        uid,
        password,
        "sale.order",
        "read",
        [[sale_order_id]],
        {"fields": ["invoice_ids"]},
    )
    invoice_ids = read_sale_order_fields[0].get("invoice_ids")

    # validate all invoices related to this sale order
    logging.info("Validating invoices related to current Sale Order...")
    models.execute_kw(
        db, uid, password, "account.invoice", "action_invoice_open", [invoice_ids]
    )

    # search the outgoing picking type
    logging.info(
        "Searching for Outgoing picking type, src location and destination location in order to manually create a delivery order..."
    )
    picking_type_id = models.execute_kw(
        db, uid, password, "stock.picking.type", "search", [[("code", "=", "outgoing")]]
    )
    # search the location and dest location
    location_id = models.execute_kw(
        db, uid, password, "stock.location", "search", [[("barcode", "=", "WH-STOCK")]]
    )
    location_dest_id = models.execute_kw(
        db, uid, password, "stock.location", "search", [[("usage", "=", "customer")]]
    )

    if picking_type_id and location_id and location_dest_id:
        picking_type_id = picking_type_id[0]
        location_id = location_id[0]
        location_dest_id = location_dest_id[0]
    else:
        logging.error("No outgoing picking type found in this database.")
        sys.exit()

    # create a delivery order
    logging.info("Manually creating a Delivery Order...")
    picking_id = models.execute_kw(
        db,
        uid,
        password,
        "stock.picking",
        "create",
        [
            {
                "partner_id": partner_id,
                "location_id": location_id,
                "location_dest_id": location_dest_id,
                "picking_type_id": picking_type_id,
                "move_ids_without_package": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_id,
                            "product_uom_qty": 1.0,
                            "name": "/",
                            "product_uom": 1,
                        },
                    )
                ],
            }
        ],
    )

    # mark as todo
    logging.info("Marking Delivery Order as Todo...")
    models.execute_kw(
        db, uid, password, "stock.picking", "action_confirm", [picking_id]
    )

    # create an inventory adjustment
    logging.info(
        "Creating inventory adjustment in order to update on hand quantity for the Test Product..."
    )
    inventory_id = models.execute_kw(
        db,
        uid,
        password,
        "stock.inventory",
        "create",
        [
            {
                "name": "INV: Test Storable Product Inventory Adjust",
                "filter": "product",
                "product_id": product_id,
                "location_id": location_id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_qty": 1.0,
                            "location_id": location_id,
                            "product_id": product_id,
                            "product_uom_id": 1,  # just gonna use the first uom here, but make sure you pass in the right one
                            "theoretical_qty": 0.0,
                        },
                    )
                ],
            }
        ],
    )

    # create an inventory adjustment wizard since inventory adjustment fails in xmlrpc
    tracking_confirmation_id = models.execute_kw(
        db,
        uid,
        password,
        "stock.track.confirmation",
        "create",
        [
            {
                "inventory_id": inventory_id,
                "tracking_line_ids": [(0, 0, {"product_id": product_id})],
            }
        ],
    )

    # confirm wizard
    models.execute_kw(
        db,
        uid,
        password,
        "stock.track.confirmation",
        "action_confirm",
        [tracking_confirmation_id],
    )

    # the following can be used if you feel lazy
    # try:
    #     models.execute_kw(
    #         db,
    #         uid,
    #         password,
    #         "stock.inventory",
    #         "action_validate",
    #         [inventory_id],
    #     )

    # except client.Fault:
    #     pass

    # check availability
    logging.info("Checking availability on the Delivery Order...")
    models.execute_kw(db, uid, password, "stock.picking", "action_assign", [picking_id])

    # read all move lines related to this picking
    read_picking_fields = models.execute_kw(
        db,
        uid,
        password,
        "stock.picking",
        "read",
        [[picking_id]],
        {"fields": ["move_ids_without_package"]},
    )
    move_ids = read_picking_fields[0].get("move_ids_without_package")

    # write quantity done to move lines
    logging.info(
        "Updating Done Qty to move lines on the Delivery Order in order to vallidate it later..."
    )
    models.execute_kw(
        db, uid, password, "stock.move", "write", [move_ids, {"quantity_done": 1.0}]
    )

    # validate
    try:
        logging.info("Validating Delivery Order...")
        models.execute_kw(
            db, uid, password, "stock.picking", "button_validate", [picking_id]
        )
    except client.Fault:
        pass

    # cancel
    # notice you can't cancel a delivery when it is done
    # maybe consult functional way of workarounds and then do it programmatically
    # models.execute_kw(
    #     db,
    #     uid,
    #     password,
    #     "stock.picking",
    #     "action_cancel",
    #     [picking_id],
    # )

    # delete
    # models.execute_kw(
    #     db,
    #     uid,
    #     password,
    #     "stock.picking",
    #     "unlink",
    #     [picking_id],
    # )

    logging.info("Done.")


if __name__ == "__main__":
    run()