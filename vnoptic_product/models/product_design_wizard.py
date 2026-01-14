from odoo import models, fields, api


class ProductDesignWizard(models.TransientModel):
    _name = 'product.design.wizard'
    _description = 'Product Design Creation Wizard'

    name = fields.Char('Tên thiết kế', required=True, size=50)
    cid = fields.Char('Mã thiết kế', size=5)
    description = fields.Text('Mô tả', size=100)

    def action_create_design(self):
        self.ensure_one()
        
        # Create the product design
        design = self.env['product.design'].create({
            'name': self.name,
            'cid': self.cid,
            'description': self.description,
            'active': True,
        })
        
        # Return action to show the created design
        return {
            'type': 'ir.actions.act_window',
            'name': 'Thiết kế sản phẩm',
            'res_model': 'product.design',
            'res_id': design.id,
            'view_mode': 'form',
            'target': 'current',
        }
