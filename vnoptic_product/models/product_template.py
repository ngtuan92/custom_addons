from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    eng_name = fields.Char("English Name")
    trade_name = fields.Char("Trade Name")

    # Price fields are defined in xnk_intergration module with x_ prefix
    # x_rt_price, x_ws_price, x_ct_price, x_or_price, x_ws_price_max, x_ws_price_min

    access_total = fields.Integer("Accessory Total")
    cid_ncc = fields.Char("Supplier code")
    unit = fields.Char("Unit")
    uses = fields.Text("Uses")
    guide = fields.Text("Guide")
    warning = fields.Text("Warning")
    preserve = fields.Text('Preserve')
    # tax_rate is defined in xnk_intergration as x_tax_percent

    supplier_id = fields.Many2one('res.partner', string='Supplier')
    group_id = fields.Many2one('product.group', string='Product Group')
    status_group_id = fields.Many2one('product.status', string='Status Product Group')
    warranty_id = fields.Many2one('xnk.warranty', 'Warranty')
    currency_zone_id = fields.Many2one('res.currency', 'Currency Zone')
    status_product_id = fields.Many2one('product.status', 'Status Product')
    brand_id = fields.Many2one('xnk.brand', 'Brand', index=True, tracking=True)
    country_id = fields.Many2one('xnk.country', 'Country of Origin')

    product_type = fields.Selection([
        ('lens', 'Lens'),
        ('opt', 'Optical Product'),
        ('accessory', 'Accessory')
    ], string='Product Type', default='lens')

    lens_ids = fields.One2many('product.lens', 'product_tmpl_id', 'Lens Details')
    opt_ids = fields.One2many('product.opt', 'product_tmpl_id', 'Optical Details')

    @api.model
    def create(self, vals):
        product_type = vals.get('product_type', 'lens')

        if product_type != 'lens':
            if 'lens_ids' in vals:
                del vals['lens_ids']

        if product_type != 'opt':
            if 'opt_ids' in vals:
                del vals['opt_ids']

        return super().create(vals)

    def write(self, vals):
        product_type = vals.get('product_type') or self.product_type

        if 'product_type' in vals:
            if vals['product_type'] != 'lens':
                self.lens_ids.unlink()
                if 'lens_ids' in vals:
                    del vals['lens_ids']

            if vals['product_type'] != 'opt':
                self.opt_ids.unlink()
                if 'opt_ids' in vals:
                    del vals['opt_ids']

        return super().write(vals)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        many2one_fields = [
            'supplier_id', 'group_id', 'status_group_id', 'warranty_id',
            'currency_zone_id', 'status_product_id', 'brand_id', 'country_id'
        ]
        
        for field in many2one_fields:
            if field in fields_list and field not in res:
                res[field] = False
        
        return res

    def action_fix_product_type(self):
        for product in self:
            if product.product_type and product.product_type != 'lens':
                continue
                
            if product.lens_ids:
                product.product_type = 'lens'
            elif product.opt_ids:
                product.product_type = 'opt'
            elif product.group_id:
                group_name = product.group_id.name
                if 'Mắt' in group_name or 'Lens' in group_name or 'lens' in group_name:
                    product.product_type = 'lens'
                elif 'Gọng' in group_name or 'Optical' in group_name or 'opt' in group_name.lower():
                    product.product_type = 'opt'
                else:
                    product.product_type = 'accessory'
            else:
                if not product.product_type:
                    product.product_type = 'accessory'
        
        return True

    @api.model
    def cron_fix_all_product_types(self):
        products = self.search([])
        products.action_fix_product_type()
        return True
