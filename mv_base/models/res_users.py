# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class Users(models.Model):
    _inherit = "res.users"

    def get_users_from_group(self, group_id):
        """
        Get user_id from `res_groups_users_rel` table.

        :param group_id: ID of the group
        :return: list of user IDs
        """
        query = """SELECT uid FROM res_groups_users_rel WHERE gid = %s"""
        self.env.cr.execute(query, (group_id,))
        return [user[0] for user in self.env.cr.fetchall()]
