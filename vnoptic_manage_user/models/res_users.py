from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        # Danh sách các field KHÔNG theo dõi (vì lý do bảo mật hoặc không cần thiết)
        IGNORED_FIELDS = ['password', 'message_ids', 'message_follower_ids']
        
        # Theo dõi tất cả các field có trong vals, trừ các field bị ignore và các field ảo
        # Tuy nhiên, nếu có field ảo liên quan đến nhóm (sel_groups, in_group), ta CẦN theo dõi 'groups_id'
        
        has_virtual_group_fields = any(k.startswith(('sel_groups_', 'in_group_')) for k in vals)
        
        fields_to_check = [
            f for f in vals 
            if f not in IGNORED_FIELDS 
            and not f.startswith(('sel_groups_', 'in_group_'))
        ]
        
        # Nếu có thay đổi nhóm qua giao diện (ảo), bắt buộc theo dõi groups_id
        if has_virtual_group_fields and 'groups_id' not in fields_to_check:
            fields_to_check.append('groups_id')
            
        if not fields_to_check:
            return super(ResUsers, self).write(vals)

        # 1. Lưu giá trị cũ trước khi ghi đè
        old_values = {}
        for user in self:
            old_values[user.id] = {}
            for field in fields_to_check:
                if field == 'groups_id':
                    # Với Many2many, lưu danh sách ID nhóm để so sánh diff
                    old_values[user.id][field] = user.groups_id.ids
                else:
                    old_values[user.id][field] = user[field]

        # 2. Gọi hàm gốc để thực hiện ghi dữ liệu
        result = super(ResUsers, self).write(vals)

        # 3. So sánh và ghi log
        LogModel = self.env['user.change.log']
        # Dùng sudo() nếu người dùng hiện tại không có quyền ghi log (tuy nhiên log do system ghi thì thường ok)
        # Ở đây ta lấy user hiện tại (env.user)
        current_user = self.env.user

        for user in self:
            for field in fields_to_check:
                old_val = old_values[user.id].get(field)
                new_val = None

                # Lấy giá trị mới
                # Lấy giá trị mới
                if field == 'groups_id':
                    # Lấy danh sách ID nhóm mới
                    new_group_ids = user.groups_id.ids
                    old_group_ids = user.groups_id.browse(old_values[user.id].get(field, [])).ids
                    
                    added = list(set(new_group_ids) - set(old_group_ids))
                    removed = list(set(old_group_ids) - set(new_group_ids))
                    
                    if added or removed:
                        # Lấy tên các nhóm
                        Group = self.env['res.groups']
                        added_names = Group.browse(added).mapped('display_name') # Dùng display_name rõ hơn
                        removed_names = Group.browse(removed).mapped('display_name')
                        
                        # Format log ngắn gọn theo style Delta/Diff
                        # Cột Mới: chứa những cái được THÊM vào
                        if added_names:
                             new_val = f"Thêm: {', '.join(added_names)}"
                        else:
                             new_val = ""
                             
                        # Cột Cũ: chứa những cái bị BỎ đi (đã mất)
                        if removed_names:
                             old_val = f"Bỏ: {', '.join(removed_names)}"
                        else:
                             old_val = ""
                    else:
                        new_val = None # Không thay đổi
                else:
                    # Các field cơ bản và relation khác
                    new_val_raw = user[field]
                    
                    if old_val != new_val_raw:
                        # Hàm helper để format giá trị hiển thị đẹp hơn
                        def format_val(val, field_name):
                            if not val:
                                return ""
                            ftype = self._fields[field_name].type
                            
                            if ftype == 'many2one':
                                return val.display_name or ''
                            elif ftype in ['many2many', 'one2many']:
                                return ', '.join(val.mapped('display_name'))
                            elif ftype == 'boolean':
                                return 'True' if val else 'False'
                            elif ftype == 'selection':
                                return dict(self._fields[field_name].selection).get(val, val)
                            else:
                                return str(val)

                        # Format lại old và new value
                        # Lưu ý: old_val hiện tại đang lưu raw value (object hoặc id) từ bước convert trước
                        # Tuy nhiên do old_values lưu object từ user[field], nên nó vẫn còn là recordset (với m2o, m2m)
                        # Trừ khi ở bước lưu old_values ta đã chưa xử lý kỹ.
                        # Check lại bước 1: old_values[user.id][field] = user[field] -> Đang lưu recordset thật.
                        
                        old_val_str = format_val(old_val, field)
                        new_val = format_val(new_val_raw, field)
                        
                        if old_val_str != new_val:
                            old_val = old_val_str
                        else:
                            new_val = None # Nếu format ra string giống nhau thì thôi (ví dụ m2m thứ tự khác nhau nhưng sort rồi, hoặc object cũ mới display_name giống nhau)
                            
                    else:
                         new_val = None

                # Nếu có thay đổi thì tạo record log
                if new_val is not None:
                    # Xử lý hiển thị active True/False cho đẹp (tuỳ chọn)
                    if field == 'active':
                        old_val = 'Active' if old_val == True or old_val == 'True' else 'Archived'
                        new_val = 'Active' if new_val == True or new_val == 'True' else 'Archived'
                    
                    # Lấy label (string) của field
                    field_label = self._fields[field].string or field

                    LogModel.create({
                        'user_id': user.id,
                        'changed_by': current_user.id,
                        'field_name': field_label,
                        'old_value': old_val or '',
                        'new_value': new_val or '',
                    })

        return result
