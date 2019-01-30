# -*- coding: utf-8 -*-

from odoo import api, fields, models, registry, SUPERUSER_ID
from ..api.CorpApi import *
from ..helper.common import *
import logging,platform
import threading
import time

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    _description = '企业微信员工'
    _order = 'wxwork_user_order'

    wxwork_id = fields.Char(string='企微用户Id', readonly=True)
    alias = fields.Char(string='别名', readonly=True)
    department_ids = fields.Many2many('hr.department', string='企微多部门', readonly=True)
    qr_code = fields.Binary(string='个人二维码', help='员工个人二维码，扫描可添加为外部联系人', readonly=True)
    wxwork_user_order = fields.Char(
        '企微用户排序',
        default='0',
        help='部门内的排序值，默认为0。数量必须和department一致，数值越大排序越前面。值范围是[0, 2^32)',
        readonly=True,
    )
    is_wxwork_employee = fields.Boolean('企微员工', readonly=True)

    @api.multi
    def sync_employee(self):
        params = self.env['ir.config_parameter'].sudo()
        corpid = params.get_param('wxwork.corpid')
        secret = params.get_param('wxwork.contacts_secret')
        sync_department_id = params.get_param('wxwork.contacts_sync_hr_department_id')
        api = CorpApi(corpid, secret)
        try:
            response = api.httpCall(
                CORP_API_TYPE['USER_LIST'],
                {
                    'department_id': sync_department_id,
                    'fetch_child': '1',
                }
            )
            start = time.time()
            for obj in response['userlist']:
                threaded_sync = threading.Thread(target=self.run, args=[obj])
                threaded_sync.start()
                # self.run(obj)
            end = time.time()
            times = end - start
            result = True
        except BaseException as e:
            print(repr(e))
            result = False
        return times,result

    @api.multi
    def run(self, obj):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            env = self.sudo().env['hr.employee']
            domain = ['|', ('active', '=', False),
                      ('active', '=', True)]
            records = env.search(
                domain + [
                    ('wxwork_id', '=', obj['userid']),
                    ('is_wxwork_employee', '=', True)],
                limit=1)

            try:
                if len(records) > 0:
                    self.update_employee(records, obj)
                else:
                    self.create_employee(records, obj)
            except Exception as e:
                print(repr(e))
            new_cr.commit()
            new_cr.close()

    @api.multi
    def create_employee(self,records, obj):
        department_ids = []
        for department in obj['department']:
            department_ids.append(self.get_employee_parent_department(department))

        img_path = self.env['ir.config_parameter'].sudo().get_param('wxwork.contacts_img_path')
        if (platform.system() == 'Windows'):
            avatar_file = img_path.replace("\\","/") + "/avatar/" + obj['userid'] + ".jpg"
            qr_code_file = img_path.replace("\\","/")  + "/qr_code/" + obj['userid'] + ".png"
        else:
            avatar_file = img_path + "avatar/" + obj['userid'] + ".jpg"
            qr_code_file = img_path + "qr_code/" + obj['userid'] + ".png"

        try:
            records.create({
                'wxwork_id': obj['userid'],
                'name': obj['name'],
                'gender': Common(obj['gender']).gender(),
                'marital': None, # 不生成婚姻状况
                'image': self.encode_image_as_base64(avatar_file),
                'mobile_phone': obj['mobile'],
                'work_phone': obj['telephone'],
                'work_email': obj['email'],
                'active': obj['enable'],
                'alias': obj['alias'],
                'department_ids': [(6, 0, department_ids)],
                'wxwork_user_order': obj['order'],
                'qr_code': self.encode_image_as_base64(qr_code_file),
                'is_wxwork_employee': True,
            })
            result = True
        except Exception as e:
            print('%s - %s' % (obj['name'], repr(e)))
            result = False
        return result

    @api.multi
    def update_employee(self,records, obj):
        department_ids = []
        for department in obj['department']:
            department_ids.append(self.get_employee_parent_department(department))
        img_path = self.env['ir.config_parameter'].sudo().get_param('wxwork.contacts_img_path')
        if (platform.system() == 'Windows'):
            avatar_file = img_path.replace("\\","/") + "/avatar/" + obj['userid'] + ".jpg"
            qr_code_file = img_path.replace("\\","/")  + "/qr_code/" + obj['userid'] + ".png"
        else:
            avatar_file = img_path + "avatar/" + obj['userid'] + ".jpg"
            qr_code_file = img_path + "qr_code/" + obj['userid'] + ".png"
        try:
            records.write({
                'name': obj['name'],
                'gender': Common(obj['gender']).gender(),
                'image': self.encode_image_as_base64(avatar_file),
                'mobile_phone': obj['mobile'],
                'work_phone': obj['telephone'],
                'work_email': obj['email'],
                'active': obj['enable'],
                'alias': obj['alias'],
                'department_ids': [(6, 0, department_ids)],
                'wxwork_user_order': obj['order'],
                'qr_code': self.encode_image_as_base64(qr_code_file),
                'is_wxwork_employee': True
            })
            result = True
        except Exception as e:
            print('%s - %s' % (obj['name'], repr(e)))
            result = False

        return result


    @api.multi
    def encode_image_as_base64(self,image_path):
        # if not self.sync_img:
        #     return None
        if not os.path.exists(image_path):
            pass
        else:
            try:
                with open(image_path, "rb") as f:
                    encoded_string = base64.b64encode(f.read())
                return encoded_string
            except BaseException as e:
                return None
                # pass

    @api.multi
    def get_employee_parent_department(self,department_id):
        try:
            departments = self.env['hr.department'].search([
                ('wxwork_department_id', '=', department_id),
                ('is_wxwork_department', '=', True)],
                limit=1)
            if len(departments) > 0:
                return departments.id
        except BaseException:
            pass


