from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    eng_name = fields.Char("English Name")
    trade_name = fields.Char("Trade Name")

    # Price fields are defined in xnk_intergration module with x_ prefix
    # x_rt_price, x_ws_price, x_ct_price, x_or_price, x_ws_price_max, x_ws_price_min

    access_total = fields.Integer("Accessory Total")
    cid_ncc = fields.Char("Supplier code")
    unit = fields.Char("Unit", default="Chiếc")
    description = fields.Text("Description")
    uses = fields.Text("Uses")
    guide = fields.Text("Guide")
    warning = fields.Text("Warning")
    preserve = fields.Text('Preserve')
    # tax_rate is defined in xnk_intergration as x_tax_percent

    supplier_id = fields.Many2one('res.partner', string='Supplier')
    group_id = fields.Many2one('product.group', string='Product Group')
    status_group_id = fields.Many2one('product.status', string='Status Product Group')
    
    # Multiple warranty fields
    warranty_id = fields.Many2one('xnk.warranty', 'Warranty')
    warranty_detail_id = fields.Many2one('xnk.warranty', 'Warranty Detail')
    warranty_retail_id = fields.Many2one('xnk.warranty', 'Warranty Retail')
    warranty_supplier_id = fields.Many2one('xnk.warranty', 'Warranty Supplier')
    
    # Currency selection for foreign currency products
    currency_selection = fields.Selection([
        ('vnd', 'VND'),
        ('usd', 'USD'),
        ('japan', 'Japan (YÊN)'),
        ('china', 'China (TỆ)')
    ], string='Currency Selection', default='vnd')
    currency_zone_id = fields.Many2one('res.currency', 'Currency Zone')
    x_currency_zone_value = fields.Float('Exchange Rate', default=1.0, digits=(12, 2))
    
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
    
    @api.onchange('currency_selection')
    def _onchange_currency_selection(self):
        """Set currency_zone_id based on selection and suggest exchange rate"""
        if self.currency_selection:
            currency_map = {
                'vnd': 'VND',
                'usd': 'USD',
                'japan': 'JPY',
                'china': 'CNY'
            }
            currency_code = currency_map.get(self.currency_selection)
            if currency_code:
                currency = self.env['res.currency'].sudo().search([('name', '=', currency_code)], limit=1)
                if currency:
                    self.currency_zone_id = currency.id
                    if self.currency_selection == 'vnd':
                        self.x_currency_zone_value = 1.0

    @api.onchange('group_id', 'brand_id')
    def _onchange_generate_product_code(self):
        """Auto-generate product code when group or brand changes"""
        from odoo.addons.vnoptic_product import utils as vnoptic_utils
        
        if self.group_id or self.brand_id:
            # Get lens_index_id from lens_ids if product_type is lens
            lens_index_id = False
            if self.product_type == 'lens' and self.lens_ids:
                lens_index_id = self.lens_ids[0].index_id.id if self.lens_ids[0].index_id else False
            
            code = vnoptic_utils.product_code_utils.generate_product_code(
                self.env,
                self.group_id.id if self.group_id else False,
                self.brand_id.id if self.brand_id else False,
                lens_index_id
            )
            self.default_code = code

    @api.model
    def create(self, vals):
        product_type = vals.get('product_type', 'lens')

        if product_type != 'lens':
            if 'lens_ids' in vals:
                del vals['lens_ids']

        if product_type != 'opt':
            if 'opt_ids' in vals:
                del vals['opt_ids']

        product = super().create(vals)
        
        # Auto-create lens/opt record if needed
        if product_type == 'lens' and not product.lens_ids:
            self.env['product.lens'].create({'product_tmpl_id': product.id})
        elif product_type == 'opt' and not product.opt_ids:
            self.env['product.opt'].create({'product_tmpl_id': product.id})
        
        return product

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
