from odoo import models, fields


class ProductGroup(models.Model):
    _name = 'product.group'
    _description = 'Product Group'
    _order = 'name'

    name = fields.Char('Group Name', required=True)
    description = fields.Text('Description', size=200)
    activated = fields.Boolean('Activated', default=True)
    cid = fields.Char("Product Code", required=True)
    group_type_id = fields.Many2one('product.group.type', string='Group Type')
