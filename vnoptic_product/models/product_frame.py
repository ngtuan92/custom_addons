from odoo import models, fields


class ProductFrame(models.Model):
    _name = 'product.frame'
    _description = 'Frame Type'
    _order = 'name'

    name = fields.Char('Frame Name', required=True, size=50)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)
