# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
from io import BytesIO
from collections import defaultdict

import requests
import urllib3
from PIL import Image

from odoo import models, fields, api, _
from odoo.exceptions import UserError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = logging.getLogger(__name__)


class ProductSync(models.Model):
    _name = 'product.sync'
    _description = 'Product Synchronization'
    _order = 'last_sync_date desc'

    name = fields.Char('Sync Name', required=True, default='Product Sync')

    # Status tracking
    last_sync_date = fields.Datetime('Last Sync Date', readonly=True)
    sync_status = fields.Selection([
        ('never', 'Never Synced'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('error', 'Error')
    ], default='never', string='Status', readonly=True)
    sync_log = fields.Text('Sync Log', readonly=True)

    total_synced = fields.Integer('Total Products Synced', readonly=True)
    total_failed = fields.Integer('Total Failed', readonly=True)
    lens_count = fields.Integer('Lens Products', readonly=True)
    opts_count = fields.Integer('Optical OPT', readonly=True)
    other_count = fields.Integer('Other Products', readonly=True)

    progress = fields.Float('Progress (%)', readonly=True, compute='_compute_progress')

    @api.depends('total_synced', 'total_failed')
    def _compute_progress(self):
        for record in self:
            total = record.total_synced + record.total_failed
            if total > 0:
                record.progress = (record.total_synced / total) * 100
            else:
                record.progress = 0

    @api.model
    def _get_api_config(self):
        return {
            'base_url': os.getenv('SPRING_BOOT_BASE_URL', 'https://localhost:8443'),
            'login_endpoint': os.getenv('API_LOGIN_ENDPOINT', '/api/auth/service-token'),
            'products_endpoint': os.getenv('API_PRODUCTS_ENDPOINT', '/api/xnk/products'),
            'service_username': os.getenv('SPRINGBOOT_SERVICE_USERNAME', 'odoo'),
            'service_password': os.getenv('SPRINGBOOT_SERVICE_PASSWORD', 'odoo'),
            'ssl_verify': os.getenv('SSL_VERIFY', 'False').lower() == 'true',
            'login_timeout': int(os.getenv('LOGIN_TIMEOUT', '30')),
            'api_timeout': int(os.getenv('API_TIMEOUT', '300')),
        }

    def _get_access_token(self):
        config = self._get_api_config()
        login_url = f"{config['base_url']}{config['login_endpoint']}"

        try:
            _logger.info(f"🔐 Getting token from: {login_url}")

            response = requests.post(
                login_url,
                json={
                    'username': config['service_username'],
                    'password': config['service_password']
                },
                verify=config['ssl_verify'],
                timeout=config['login_timeout']
            )

            response.raise_for_status()
            data = response.json()
            token = data.get('token')

            if not token:
                raise UserError(_('Login failed: No token received'))

            _logger.info("✅ Token obtained successfully")
            return token

        except requests.exceptions.RequestException as e:
            error_msg = f"Authentication failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            raise UserError(_(error_msg))

    def _fetch_products_from_api(self, token):
        config = self._get_api_config()
        api_url = f"{config['base_url']}{config['products_endpoint']}"

        try:
            _logger.info(f"📡 Fetching products from: {api_url}")

            response = requests.get(
                api_url,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                verify=config['ssl_verify'],
                timeout=config['api_timeout']
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            raise UserError(_(error_msg))

    def _parse_api_response(self, api_response):
        _logger.info(f"📦 Parsing response type: {type(api_response)}")

        products_data = None

        if isinstance(api_response, dict):
            if 'products' in api_response:
                products_str = api_response['products']
                if isinstance(products_str, str):
                    try:
                        products_data = json.loads(products_str)
                        _logger.info(f"✅ Parsed JSON string: {len(products_data)} items")
                    except json.JSONDecodeError as e:
                        raise UserError(f"Invalid JSON in 'products' field: {e}")
                elif isinstance(products_str, list):
                    products_data = products_str
                    _logger.info(f"✅ Products already array: {len(products_data)} items")
            elif 'content' in api_response:
                products_data = api_response['content']
                _logger.info(f"✅ Found 'content' key: {len(products_data)} items")
            elif 'data' in api_response:
                products_data = api_response['data']
                _logger.info(f"✅ Found 'data' key: {len(products_data)} items")
        elif isinstance(api_response, list):
            products_data = api_response
            _logger.info(f"✅ Direct array: {len(products_data)} items")

        if not products_data:
            raise UserError(_('Cannot extract products from API response'))
        if not isinstance(products_data, list):
            raise UserError(_('Products data must be an array'))
        if len(products_data) == 0:
            raise UserError(_('API returned 0 products'))

        return products_data


    def _preload_all_data(self):

        _logger.info("📦 Pre-loading existing data...")

        cache = {
            'products': {},
            'categories': {},
            'brands': {},
            'countries': {},
            'warranties': {},
            'taxes': {},
            'suppliers': {},
            'supplier_info': defaultdict(dict),
        }

        products = self.env['product.template'].search_read(
            [('default_code', '!=', False)],
            ['id', 'default_code']
        )
        cache['products'] = {p['default_code']: p['id'] for p in products}
        _logger.info(f"  ✅ Loaded {len(cache['products'])} existing products")

        categories = self.env['product.category'].search_read(
            [],
            ['id', 'name', 'parent_id']
        )
        for cat in categories:
            parent_id = cat['parent_id'][0] if cat['parent_id'] else False
            cache['categories'][(cat['name'], parent_id)] = cat['id']
        _logger.info(f"  ✅ Loaded {len(cache['categories'])} categories")

        if 'xnk.brand' in self.env:
            brands = self.env['xnk.brand'].search_read([], ['id', 'code'])
            cache['brands'] = {b['code']: b['id'] for b in brands}
            _logger.info(f"  ✅ Loaded {len(cache['brands'])} brands")

        if 'xnk.country' in self.env:
            countries = self.env['xnk.country'].search_read([], ['id', 'code'])
            cache['countries'] = {c['code']: c['id'] for c in countries}
            _logger.info(f"  ✅ Loaded {len(cache['countries'])} countries")

        if 'xnk.warranty' in self.env:
            warranties = self.env['xnk.warranty'].search_read([], ['id', 'code'])
            cache['warranties'] = {w['code']: w['id'] for w in warranties}
            _logger.info(f"  ✅ Loaded {len(cache['warranties'])} warranties")

        taxes = self.env['account.tax'].search_read(
            [('type_tax_use', '=', 'sale')],
            ['id', 'name']
        )
        cache['taxes'] = {t['name']: t['id'] for t in taxes}
        _logger.info(f"  ✅ Loaded {len(cache['taxes'])} taxes")

        suppliers = self.env['res.partner'].search_read(
            [('ref', '!=', False), ('supplier_rank', '>', 0)],
            ['id', 'ref']
        )
        cache['suppliers'] = {s['ref']: s['id'] for s in suppliers}
        _logger.info(f"  ✅ Loaded {len(cache['suppliers'])} suppliers")

        supplier_infos = self.env['product.supplierinfo'].search_read(
            [],
            ['product_tmpl_id', 'partner_id', 'id']
        )
        for si in supplier_infos:
            tmpl_id = si['product_tmpl_id'][0]
            partner_id = si['partner_id'][0]
            cache['supplier_info'][tmpl_id][partner_id] = si['id']
        _logger.info(f"  ✅ Loaded {len(supplier_infos)} supplier infos")

        return cache

    def _get_or_create_from_cache(self, model_name, cache_key, code, name, cache, extra_vals=None):
        if code in cache[cache_key]:
            return cache[cache_key][code]

        vals = {'name': name, 'code': code}
        if extra_vals:
            vals.update(extra_vals)

        new_record = self.env[model_name].create(vals)
        cache[cache_key][code] = new_record.id

        return new_record.id

    def sync_products_from_springboot(self):
        self.ensure_one()

        try:
            # Update status
            self.write({
                'sync_status': 'in_progress',
                'sync_log': 'Starting sync...'
            })
            self.env.cr.commit()

            _logger.info("=" * 80)
            _logger.info("🚀 Starting OPTIMIZED product synchronization...")

            token = self._get_access_token()

            api_response = self._fetch_products_from_api(token)

            products_data = self._parse_api_response(api_response)

            _logger.info(f"📦 Processing {len(products_data)} products...")

            cache = self._preload_all_data()

            success, failed, stats = self._process_products_optimized(products_data, cache)

            log_message = self._generate_sync_log(success, failed, stats)

            self.write({
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'success',
                'total_synced': success,
                'total_failed': failed,
                'lens_count': stats['lens'],
                'opts_count': stats['opt'],
                'other_count': stats['accessory'],
                'sync_log': log_message
            })

            self.env.cr.commit()

            _logger.info("=" * 80)
            _logger.info(f"✅ SYNC COMPLETED: {success} OK, {failed} failed")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Sync Successful'),
                    'message': f'Synced {success} products! ({stats["lens"]} Lens, {stats["opt"]} OPT, {stats["accessory"]} Accessories)',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"❌ Sync failed: {error_msg}")
            _logger.exception("Full traceback:")

            self.write({
                'sync_status': 'error',
                'sync_log': f"❌ ERROR:\n\n{error_msg}"
            })
            self.env.cr.commit()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Sync Failed'),
                    'message': error_msg[:200],
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _process_products_optimized(self, products_data, cache):

        success = 0
        failed = 0
        stats = {'lens': 0, 'opt': 0, 'accessory': 0}

        to_create = []
        to_update = []
        to_create_lens = []
        to_create_opt = []

        total = len(products_data)

        for idx, product_data in enumerate(products_data, 1):
            try:
                if idx % 100 == 0:
                    _logger.info(f"📊 Progress: {idx}/{total} ({(idx / total) * 100:.1f}%)")

                vals, product_type, product_id = self._prepare_product_vals_optimized(product_data, cache)

                if product_id:
                    to_update.append((product_id, vals, product_type))
                else:
                    to_create.append((vals, product_type))

                if product_type == 'lens':
                    stats['lens'] += 1
                elif product_type == 'opt':
                    stats['opt'] += 1
                else:
                    stats['accessory'] += 1

                success += 1

            except Exception as e:
                failed += 1
                cid = product_data.get('cid', 'Unknown')
                _logger.error(f"❌ Error processing product {cid}: {e}")
                continue

        if to_create:
            _logger.info(f"💾 Batch creating {len(to_create)} products...")
            created_products = self.env['product.template'].create([v[0] for v in to_create])

            for idx, record in enumerate(created_products):
                product_type = to_create[idx][1]
                if product_type == 'lens' and 'product.lens' in self.env:
                    to_create_lens.append({'product_tmpl_id': record.id})
                elif product_type == 'opt' and 'product.opt' in self.env:
                    to_create_opt.append({'product_tmpl_id': record.id})

            if to_create_lens:
                self.env['product.lens'].create(to_create_lens)
            if to_create_opt:
                self.env['product.opt'].create(to_create_opt)

        if to_update:
            _logger.info(f"💾 Batch updating {len(to_update)} products...")
            for product_id, vals, product_type in to_update:
                self.env['product.template'].browse(product_id).write(vals)

        return success, failed, stats

    def _prepare_product_vals_optimized(self, p, cache):

        if not isinstance(p, dict):
            raise ValueError("Invalid product data type")

        cid = p.get('cid', '').strip()
        if not cid:
            raise ValueError("Missing product CID")

        name = p.get('fullname') or 'Unknown Product'

        product_id = cache['products'].get(cid)

        groupdto = p.get('groupdto') or {}
        group_type_dto = groupdto.get('groupTypedto') or {}
        group_type_name = group_type_dto.get('name', 'Khác')

        category_map = {
            'Mắt': ('Lens Products', 'lens'),
            'Gọng': ('Optical OPT', 'opt'),
            'Khác': ('Accessories', 'accessory')
        }

        main_category, product_type = category_map.get(
            group_type_name,
            ('Accessories', 'accessory')
        )

        categ_id = self._get_category_from_cache(
            groupdto.get('name', 'All Products'),
            cache,
            parent_name=main_category
        )

        # BRAND
        brand_cid = (p.get('tmdto') or {}).get('cid')
        brand_name = (p.get('tmdto') or {}).get('name')
        brand_id = False
        if brand_cid and brand_name and 'xnk.brand' in self.env:
            brand_id = self._get_or_create_from_cache(
                'xnk.brand',
                'brands',
                brand_cid,
                brand_name,
                cache,  # <-- quan trọng
            )


        # SUPPLIER
        supplierdto = p.get('supplierdto') or {}
        supplier_id = False
        supplier_details = supplierdto.get('supplierDetailDTOS', [])

        if supplier_details and len(supplier_details) > 0:
            detail = supplier_details[0]
            supplier_cid = detail.get('cid')  # "5002"
            supplier_name = detail.get('name')  # "DANYANG POWER WAY..."

            if supplier_cid and supplier_name:
                if supplier_cid in cache['suppliers']:
                    supplier_id = cache['suppliers'][supplier_cid]
                else:
                    # Tạo mới supplier
                    supplier = self.env['res.partner'].create({
                        'name': supplier_name,
                        'ref': supplier_cid,
                        'supplier_rank': 1,
                        'is_company': True,
                        'phone': detail.get('phone', ''),
                        'email': detail.get('mail', ''),
                        'street': detail.get('address', ''),
                    })
                    supplier_id = supplier.id
                    cache['suppliers'][supplier_cid] = supplier_id

        # COUNTRY
        country_cid = (p.get('codto') or {}).get('cid')
        country_name = (p.get('codto') or {}).get('name')
        country_id = False
        if country_cid and country_name and 'xnk.country' in self.env:
            country_id = self._get_or_create_from_cache(
                'xnk.country',
                'countries',
                country_cid,
                country_name,
                cache,
            )


        warranty_dto = p.get('warrantydto')
        warranty_id = False
        if warranty_dto and isinstance(warranty_dto, dict):
            warranty_cid = warranty_dto.get('cid')
            warranty_name = warranty_dto.get('name')
            if warranty_cid and warranty_name and 'xnk.warranty' in self.env:
                warranty_id = self._get_or_create_from_cache(
                    'xnk.warranty',
                    'warranties',
                    warranty_cid,
                    warranty_name,
                    cache,
                    extra_vals={
                        'description': warranty_dto.get('description', ''),
                        'value': int(warranty_dto.get('value', 0))
                    }
                )

        # TAX
        tax_percent = float(p.get('tax') or 0)
        tax_id = False
        if tax_percent and tax_percent > 0:
            tax_name = f"Tax {tax_percent}%"
            if tax_name in cache['taxes']:
                tax_id = cache['taxes'][tax_name]
            else:
                tax = self.env['account.tax'].create({
                    'name': tax_name,
                    'amount': tax_percent,
                    'amount_type': 'percent',
                    'type_tax_use': 'sale'
                })
                cache['taxes'][tax_name] = tax.id
                tax_id = tax.id



        taxes_ids = [(6, 0, [tax_id])] if tax_id else False

        rt_price = float(p.get('rtPrice') or 0)
        ws_price = float(p.get('wsPrice') or 0)
        ct_price = float(p.get('ctPrice') or 0)
        or_price = float(p.get('orPrice') or 0)

        uom_id = self.env.ref('uom.product_uom_unit').id

        vals = {
            'name': name,
            'default_code': cid,
            'type': 'product',
            'categ_id': categ_id,
            'uom_id': uom_id,
            'uom_po_id': uom_id,
            'list_price': rt_price,
            'standard_price': or_price,
            'taxes_id': taxes_ids,
        }

        # Add Many2one fields directly to vals
        vals.update({
            'brand_id': brand_id,
            'supplier_id': supplier_id,
            'country_id': country_id,
            'warranty_id': warranty_id,
        })

        custom_fields = {
            'product_type': product_type,
            'x_eng_name': p.get('engName', ''),
            'x_trade_name': p.get('tradeName', ''),
            'x_note_long': p.get('note', ''),
            'x_uses': p.get('uses', ''),
            'x_guide': p.get('guide', ''),
            'x_warning': p.get('warning', ''),
            'x_preserve': p.get('preserve', ''),
            'x_cid_ncc': p.get('cidNcc', ''),
            'x_accessory_total': int(p.get('accessoryTotal') or 0),
            'x_status_name': (p.get('statusProductdto') or {}).get('name', ''),
            'x_tax_percent': tax_percent,
            'x_currency_zone_code': (p.get('currencyZoneDTO') or {}).get('cid', ''),
            'x_currency_zone_value': float((p.get('currencyZoneDTO') or {}).get('value') or 0),
            'x_ws_price': ws_price,
            'x_ct_price': ct_price,
            'x_or_price': or_price,
            'x_group_type_name': group_type_name,
            'x_supplier_info_id': cache['supplier_info'].get(product_id, False),
        }

        ProductTemplate = self.env['product.template']
        for field_name, field_value in custom_fields.items():
            if field_name in ProductTemplate._fields:
                vals[field_name] = field_value

        return vals, product_type, product_id

    def _get_category_from_cache(self, category_name, cache, parent_name=None):
        if not category_name:
            return self.env.ref('product.product_category_all').id

        parent_id = False
        if parent_name:
            cache_key = (parent_name, False)
            if cache_key in cache['categories']:
                parent_id = cache['categories'][cache_key]
            else:
                parent = self.env['product.category'].create({'name': parent_name})
                parent_id = parent.id
                cache['categories'][cache_key] = parent_id

        cache_key = (category_name, parent_id)
        if cache_key in cache['categories']:
            return cache['categories'][cache_key]

        vals = {'name': category_name}
        if parent_id:
            vals['parent_id'] = parent_id

        category = self.env['product.category'].create(vals)
        cache['categories'][cache_key] = category.id

        return category.id

    def _generate_sync_log(self, success, failed, stats):
        total = success + failed
        success_rate = (success / total * 100) if total > 0 else 0

        return f"""✅ SYNC COMPLETED!

Total: {success} synced, {failed} failed

Categories:
  • Lens: {stats['lens']}
  • OPT: {stats['opt']}
  • Accessories: {stats['accessory']}

Date: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    def test_api_connection(self):
        self.ensure_one()

        try:
            token = self._get_access_token()
            api_response = self._fetch_products_from_api(token)
            products = self._parse_api_response(api_response)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Connection Successful'),
                    'message': f'Found {len(products)} products available on API',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Connection Failed'),
                    'message': str(e)[:200],
                    'type': 'danger',
                    'sticky': True,
                }
            }
