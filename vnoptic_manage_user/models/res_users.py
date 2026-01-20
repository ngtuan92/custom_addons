from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        # Danh sách các field KHÔNG theo dõi (vì lý do bảo mật hoặc không cần thiết)
        IGNORED_FIELDS = ['password', 'message_ids', 'message_follower_ids']
        
        # Theo dõi tất cả các field có trong vals, trừ các field bị ignore
        fields_to_check = [f for f in vals if f not in IGNORED_FIELDS]
        
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
                        
                        # Format log ngắn gọn
                        msg_parts = []
                        if added_names:
                            msg_parts.append(f"Thêm: {', '.join(added_names)}")
                        if removed_names:
                            msg_parts.append(f"Bỏ: {', '.join(removed_names)}")
                            
                        new_val = "\n".join(msg_parts)
                        old_val = "" # Với diff log kiểu này, old_val có thể để trống hoặc ghi chú gì đó
                    else:
                        new_val = None # Không thay đổi
                else:
                    # Các field cơ bản
                    new_val = user[field]
                    if old_val != new_val:
                         # Convert sang string để lưu log
                        new_val = str(new_val)
                        old_val = str(old_val)
                    else:
                        new_val = None # Đánh dấu không thay đổi để bỏ qua

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
