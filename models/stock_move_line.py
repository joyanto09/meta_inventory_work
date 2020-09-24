# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
from odoo.tools.float_utils import float_round, float_compare, float_is_zero
from re import findall as regex_findall, split as regex_split

class StockMoveLineEngineChassis(models.Model):

    _inherit = "stock.move.line"
    _description = "Show Engine Chassis Number"

    #Purchase
    lot_name = fields.Char('Lot/Serial Number Name', default=lambda self: self.env['ir.sequence'].next_by_code('stock.lot.moveline.serial'),
        required=False, help="Unique Lot/Serial Number")
    chassis_number = fields.Char(string="Chassis Number")
    engine_number = fields.Char(string="Motor Number")
    battery_number = fields.Char(string="Battery Number")

    chassis_active = fields.Boolean(string="Chassis Active")
    engine_active = fields.Boolean(string="Motor Active")
    battery_active = fields.Boolean(string="Battery Active")

    search_value_number = fields.Boolean(string=".", default=False)


    @api.onchange('search_value_number')
    def get_all_numbers(self):
        if self.search_value_number == True:
            get_all_value = self.env['stock.production.lot'].search(
                [('chassis_number', '=', self.chassis_number)])

            get_all_value_engine = self.env['stock.production.lot'].search(
                [('engine_number', '=', self.engine_number)])

            get_all_value_battery = self.env['stock.production.lot'].search(
                [('battery_number', '=', self.battery_number)])

            if self.chassis_number != False:
                for item in get_all_value:
                    self.lot_id = item.id
                    # self.chassis_number = str(item.chassis_number)
                    self.engine_number = item.engine_number
                    self.battery_number = item.battery_number

            elif self.engine_number != False:
                for items in get_all_value_engine:
                    self.lot_id = items.id
                    self.chassis_number = items.chassis_number
                    # self.engine_number = str(items.engine_number)
                    self.battery_number = items.battery_number

            elif self.battery_number != False:
                for itemsb in get_all_value_battery:
                    self.lot_id = itemsb.id
                    self.chassis_number = itemsb.chassis_number
                    self.engine_number = itemsb.engine_number
                    # self.battery_number = str(itemsb.battery_number)

            else:
                self.chassis_number = ''
                self.engine_number = ''
                self.battery_number = ''
                self.lot_id = False
        else:
            self.chassis_number = ''
            self.engine_number = ''
            self.battery_number = ''
            self.lot_id = False



    def _action_done(self):
        """ This method is called during a move's `action_done`. It'll actually move a quant from
        the source location to the destination location, and unreserve if needed in the source
        location.

        This method is intended to be called on all the move lines of a move. This method is not
        intended to be called when editing a `done` move (that's what the override of `write` here
        is done.
        """
        Quant = self.env['stock.quant']

        # First, we loop over all the move lines to do a preliminary check: `qty_done` should not
        # be negative and, according to the presence of a picking type or a linked inventory
        # adjustment, enforce some rules on the `lot_id` field. If `qty_done` is null, we unlink
        # the line. It is mandatory in order to free the reservation and correctly apply
        # `action_done` on the next move lines.
        ml_to_delete = self.env['stock.move.line']
        for ml in self:
            # Check here if `ml.qty_done` respects the rounding of `ml.product_uom_id`.
            uom_qty = float_round(ml.qty_done, precision_rounding=ml.product_uom_id.rounding, rounding_method='HALF-UP')
            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            qty_done = float_round(ml.qty_done, precision_digits=precision_digits, rounding_method='HALF-UP')
            if float_compare(uom_qty, qty_done, precision_digits=precision_digits) != 0:
                raise UserError(_('The quantity done for the product "%s" doesn\'t respect the rounding precision \
                                  defined on the unit of measure "%s". Please change the quantity done or the \
                                  rounding precision of your unit of measure.') % (ml.product_id.display_name, ml.product_uom_id.name))

            qty_done_float_compared = float_compare(ml.qty_done, 0, precision_rounding=ml.product_uom_id.rounding)
            if qty_done_float_compared > 0:
                if ml.product_id.tracking != 'none':
                    picking_type_id = ml.move_id.picking_type_id
                    if picking_type_id:
                        if picking_type_id.use_create_lots:
                            # If a picking type is linked, we may have to create a production lot on
                            # the fly before assigning it to the move line if the user checked both
                            # `use_create_lots` and `use_existing_lots`.
                            if ml.lot_name and not ml.lot_id:
                                # chsis_engine_name = self.env['stock.production.lot'].search([('chassis_number', '=', ml.chassis_number) and ('engine_number', '=', ml.engine_number) and ('battery_number', '=', ml.battery_number)])
                                # if chsis_engine_name:
                                #     raise UserError(_('Chassis Number And Engine Number is Must Be Unique'))
                                # else:
                                lot = self.env['stock.production.lot'].create(
                                    {'name': ml.lot_name, 'product_id': ml.product_id.id, 'company_id': ml.move_id.company_id.id,
                                        'chassis_number': ml.chassis_number, 'engine_number': ml.engine_number, 'battery_number': ml.battery_number}
                                )
                                ml.write({'lot_id': lot.id})
                        elif not picking_type_id.use_create_lots and not picking_type_id.use_existing_lots:
                            # If the user disabled both `use_create_lots` and `use_existing_lots`
                            # checkboxes on the picking type, he's allowed to enter tracked
                            # products without a `lot_id`.
                            continue
                    elif ml.move_id.inventory_id:
                        # If an inventory adjustment is linked, the user is allowed to enter
                        # tracked products without a `lot_id`.
                        continue

                    if not ml.lot_id:
                        raise UserError(_('You need to supply a Lot/Serial number for product %s.') % ml.product_id.display_name)
            elif qty_done_float_compared < 0:
                raise UserError(_('No negative quantities allowed'))
            else:
                ml_to_delete |= ml
        ml_to_delete.unlink()

        (self - ml_to_delete)._check_company()

        # Now, we can actually move the quant.
        done_ml = self.env['stock.move.line']
        for ml in self - ml_to_delete:
            if ml.product_id.type == 'product':
                rounding = ml.product_uom_id.rounding

                # if this move line is force assigned, unreserve elsewhere if needed
                if not ml._should_bypass_reservation(ml.location_id) and float_compare(ml.qty_done, ml.product_uom_qty, precision_rounding=rounding) > 0:
                    qty_done_product_uom = ml.product_uom_id._compute_quantity(ml.qty_done, ml.product_id.uom_id, rounding_method='HALF-UP')
                    extra_qty = qty_done_product_uom - ml.product_qty
                    ml._free_reservation(ml.product_id, ml.location_id, extra_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id, ml_to_ignore=done_ml)
                # unreserve what's been reserved
                if not ml._should_bypass_reservation(ml.location_id) and ml.product_id.type == 'product' and ml.product_qty:
                    try:
                        Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                    except UserError:
                        Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)

                # move what's been actually done
                quantity = ml.product_uom_id._compute_quantity(ml.qty_done, ml.move_id.product_id.uom_id, rounding_method='HALF-UP')
                available_qty, in_date = Quant._update_available_quantity(ml.product_id, ml.location_id, -quantity, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id)
                if available_qty < 0 and ml.lot_id:
                    # see if we can compensate the negative quants with some untracked quants
                    untracked_qty = Quant._get_available_quantity(ml.product_id, ml.location_id, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                    if untracked_qty:
                        taken_from_untracked_qty = min(untracked_qty, abs(quantity))
                        Quant._update_available_quantity(ml.product_id, ml.location_id, -taken_from_untracked_qty, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id)
                        Quant._update_available_quantity(ml.product_id, ml.location_id, taken_from_untracked_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id)
                Quant._update_available_quantity(ml.product_id, ml.location_dest_id, quantity, lot_id=ml.lot_id, package_id=ml.result_package_id, owner_id=ml.owner_id, in_date=in_date)
            done_ml |= ml
        # Reset the reserved quantity as we just moved it to the destination location.
        (self - ml_to_delete).with_context(bypass_reservation_update=True).write({
            'product_uom_qty': 0.00,
            'date': fields.Datetime.now(),
        })



# class StockMoveInheritate(models.Model):
#
#     _inherit = "stock.move"
#     _description = "Stock Move Inherit"
#
#     def action_assign_serial_show_details(self):
#         """ On `self.move_line_ids`, assign `lot_name` according to
#         `self.next_serial` before returning `self.action_show_details`.
#         """
#         self.ensure_one()
#         self.next_serial = self.picking_id.name + "-" + "1"
#
#         if not self.next_serial:
#             raise UserError(_("You need to set a Serial Number before generating more."))
#         self._generate_serial_numbers()
#         return self.action_show_details()




    # @api.onchange('chassis_number')
    # def get_engine_number(self):
    #     chassis_number = self.chassis_number
    #
    #     if chassis_number:
    #         self.engine_number = chassis_number.engine_number
    #     else:
    #         self.engine_number = 'N/A'

    ###################################################
    # @api.onchange('battery_number')
    # def get_battery_active(self):
    #     if self.battery_number != False:
    #         self.battery_active = True
    #     else:
    #         self.battery_active = False

    # @api.onchange('sales_chassis_number', 'sales_engine_number')
    # def get_value_for_lot(self):
    #     get_all_value = self.env['stock.production.lot'].search(
    #         [('chassis_number', '=', self.sales_chassis_number)])
    #
    #     get_all_value_engine = self.env['stock.production.lot'].search(
    #         [('engine_number', '=', self.sales_engine_number)])
    #
    #     if self.sales_chassis_number != False:
    #         for item in get_all_value:
    #             self.sales_engine_number = str(item.engine_number)
    #             # self.search_value_number = True
    #             self.lot_id = item.id
    #             self.chassis_number = str(item.chassis_number)
    #             self.engine_number = str(item.engine_number)
    #
    #     elif self.sales_engine_number != False:
    #         for items in get_all_value_engine:
    #             self.sales_chassis_number = str(items.chassis_number)
    #             # self.search_value_number = True
    #             self.lot_id = items.id
    #             self.chassis_number = str(items.chassis_number)
    #             self.engine_number = str(items.engine_number)
    #
    #     else:
    #         self.sales_chassis_number = ''
    #         self.sales_engine_number = ''
    #         self.lot_id = False
    #         self.chassis_number = ''
    #         self.engine_number = ''

    # @api.onchange('sales_battery_number')
    # def get_value_for_lot_battery(self):
    #     get_all_battery_value = self.env['stock.production.lot'].search(
    #         [('battery_number', '=', self.sales_battery_number)])
    #
    #     if self.sales_battery_number != False:
    #         for bitem in get_all_battery_value:
    #             self.lot_id = bitem.id
    #     else:
    #         self.lot_id = False

