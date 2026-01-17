# -*- coding: utf-8 -*-
{
    'name': 'VNOPTIC Inventory Statistic',
    'version': '16.0.1.0.0',
    'category': 'Warehouse',
    'summary': 'Inventory Dashboard SPH x CYL',
    'description': "Inventory Statistic Dashboard for VNOPTIC",
    'author': 'VNOPTIC Team',
    'website': '',
    
    # Phụ thuộc vào các module gốc và module custom của dự án
    'depends': [
        'base',
        'stock',              # Để tích hợp vào menu Kho
        'vnoptic_product',    # Lấy thông tin SPH/CYL, Index
        'xnk_intergration',   # Lấy thông tin Brand (xnk.brand)
    ],
    
    # Danh sách các file data (view, security, data...)
    'data': [
        'security/ir.model.access.csv',          # Phân quyền truy cập
        'views/inventory_statistic_view.xml',    # Giao diện dashboard
    ],
    
    # Cấu hình APP
    'installable': True,
    'application': False,  # <--- FALSE: Không hiện icon App ngoài màn hình chính (theo yêu cầu)
    'auto_install': False,
    'license': 'LGPL-3',
}
