# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools

class StockProductionLotChassisEngine(models.Model):

    _inherit = "stock.production.lot"
    _description = "Stock Production Lot Chassis and Engine Number"

    chassis_number = fields.Char('Chassis Number', default="",
                       readonly=False, required=False,)
    engine_number = fields.Char(string="Motor Number", default="",
                                readonly=False, required=False,)

    battery_number = fields.Char(string="Battery Number", default="",
                                readonly=False, required=False, )


