from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        # Danh sách các field cần theo dõi
        TRACKED_FIELDS = ['active', 'name', 'login', 'email', 'groups_id']
        
        # Chỉ xử lý nếu có field nằm trong danh sách theo dõi
        fields_to_check = [f for f in vals if f in TRACKED_FIELDS]
        
        if not fields_to_check:
            return super(ResUsers, self).write(vals)

        # 1. Lưu giá trị cũ trước khi ghi đè
        old_values = {}
        for user in self:
            old_values[user.id] = {}
            for field in fields_to_check:
                if field == 'groups_id':
                    # Với Many2many, lưu danh sách tên nhóm để dễ đọc
                    group_names = user.groups_id.mapped('name')
                    old_values[user.id][field] = ', '.join(sorted(group_names))
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
                if field == 'groups_id':
                     # Lấy danh sách tên nhóm mới sau khi đã save
                    new_group_names = user.groups_id.mapped('name')
                    new_val_str = ', '.join(sorted(new_group_names))
                    
                    # Chỉ ghi log nếu danh sách nhóm thực sự thay đổi
                    if old_val != new_val_str:
                        new_val = new_val_str
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
