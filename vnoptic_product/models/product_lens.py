from odoo import models, fields


class ProductLens(models.Model):
    _name = 'product.lens'
    _description = 'Lens Product'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    product_id = fields.Many2one('product.product', string='Product')

    prism = fields.Char('Prism', size=50)
    base = fields.Char('Base', size=50)
    axis = fields.Char('Axis', size=50)
    sph = fields.Char('Sph', size=50)
    cyl = fields.Char('Cyl', size=50)
    len_add = fields.Char('Lens Add', size=50)
    diameter = fields.Char('Diameter', size=50)
    corridor = fields.Char('Corridor', size=50)
    abbe = fields.Char('Abbe', size=50)
    polarized = fields.Char('Polarized', size=50)
    prism_base = fields.Char('Prism Base', size=50)
    color_int = fields.Char('Color Intensity', size=50)
    mir_coating = fields.Char('Mirror Coating', size=50)

    design1_id = fields.Many2one('product.design', string='Design1')
    design2_id = fields.Many2one('product.design', string='Design2')
    uv_id = fields.Many2one('product.uv', string='UV')
    cl_hmc_id = fields.Many2one('product.cl', string='CL HMC')
    cl_pho_id = fields.Many2one('product.cl', string='CL Pho')
    cl_tint_id = fields.Many2one('product.cl', string='CL Tint')
    index_id = fields.Many2one('product.lens.index', string='Index')
    material_id = fields.Many2one('product.material', string='Material')

    coating_ids = fields.Many2many('product.coating', 'lens_coating_rel',
                                   'lens_id', 'coating_id', 'Coatings')
