from odoo import api, fields, models , _
from odoo.exceptions import UserError, ValidationError
from odoo.service import db
import odoo

import datetime
import os
import logging


class DatabaseAutobackup(models .Model):
    _name = "doyenhub.database.backup"
    _description = "Automatic Database Backup"
    
    name = fields.Char(string='Name', required=True)
    db_name = fields.Char(string='Database Name', required=True)
    master_pwd = fields.Char(string='Master Password', required=True)
    backup_format = fields.Selection([
        ('zip', 'Zip'),
        ('dump', 'Dump')
    ], string='Backup Format', default='zip', required=True)
    backup_destination = fields.Selection([
        ('local', 'Local Storage')
    ], string='Backup Destination')
    backup_path = fields.Char(string='Backup Path', help='Local storage directory path')
    backup_filename = fields.Char(string='Backup Filename', help='For Storing generated backup filename')
    active = fields.Boolean(default=True)
    auto_remove = fields.Boolean(string='Remove Old Backups')
    days_to_remove = fields.Integer(string='Remove After',
                                    help='Automatically delete stored backups after this specified number of days')
    
    
    @api.constrains('db_name')
    def _check_db_credentials(self):
        """
        Validate entered database name and master password
        """
        database_list = db.list_dbs()
        if self.db_name not in database_list:
            raise ValidationError(_("Invalid Database Name!"))
        try:
            odoo.service.db.check_super(self.master_pwd)
        except Exception:
            raise ValidationError(_("Invalid Master Password!"))



    def _schedule_auto_backup(self):
        """
        Function for generating and storing backup
        Database backup for all the active records in backup configuration model will be created
        """
        records = self.search([])
        for rec in records:
            backup_time = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = "%s_%s.%s" % (rec.db_name, backup_time, rec.backup_format)
            rec.backup_filename = backup_filename
            # Local backup
            if rec.backup_destination == 'local':
                try:
                    if not os.path.isdir(rec.backup_path):
                        os.makedirs(rec.backup_path)
                    backup_file = os.path.join(rec.backup_path, backup_filename)
                    f = open(backup_file, "wb")
                    odoo.service.db.dump_db(rec.db_name, f, rec.backup_format)
                    f.close()
                    # remove older backups
                    if rec.auto_remove:
                        for filename in os.listdir(rec.backup_path):
                            file = os.path.join(rec.backup_path, filename)
                            create_time = datetime.datetime.fromtimestamp(os.path.getctime(file))
                            backup_duration = datetime.datetime.utcnow() - create_time
                            if backup_duration.days >= rec.days_to_remove:
                                os.remove(file)
                except Exception as e:
                    logging.info("/////////////////     BACKUP DB ERROR    /////////////////////////")
                    logging.info(e)
            else:
                print("errrrorrrr------------------------------------------")

