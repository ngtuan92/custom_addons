{
    "name": "VNOPTIC Products",
    "version": "16.0.1.0.0",
    "summary": "Lens & Optical product management",
    "author": "Your Company",
    "depends": ["product", "base", "xnk_intergration"],
    "data": [
        'data/product_group_type_data.xml',
        'security/ir.model.access.csv',
        # Menu gốc phải load đầu tiên
        'views/menu_root.xml',
        # Views và Actions (phải load trước menu chi tiết)
        'views/product_status_views.xml',
        'views/product_external_actions.xml',
        'views/product_warranty_views.xml',
        'views/product_template_views.xml',
        'views/product_opt_views.xml',
        'views/product_fix_action.xml',
        'views/product_color_views.xml',
        'views/product_design_views.xml',
        'views/product_material_views.xml',
        'views/product_creation_views.xml',
        'views/product_creation_wizard_action.xml',
        'views/product_actions.xml',
        'views/product_group_views.xml',
        'views/test_action.xml',
        # Menu (phải load cuối cùng vì tham chiếu đến các action ở trên)
        'views/menu.xml',
    ],
    "installable": True,
    "application": True,
}
