from odoo.addons.web.controllers.domain import Domain

from odoo import http, _
from odoo.http import Controller, request
from odoo.tools.safe_eval import safe_eval


class ksdomainfix(Domain):
        # to validate our uid and mycompany based domain
    @http.route('/web/domain/validate', type='json', auth="user")
    def validate(self, model, domain):
        ks_uid_domain = str(domain)
        if ks_uid_domain and "%UID" in ks_uid_domain:
            ks_domain =  ks_uid_domain.replace("%UID", str(request.env.user.id))
            return super().validate(model,safe_eval(ks_domain))
        elif ks_uid_domain and "%MYCOMPANY" in ks_uid_domain:
            ks_domain =  ks_uid_domain.replace("%MYCOMPANY", str(request.env.company.id))
            return super().validate(model,safe_eval(ks_domain))
        else:
            return super().validate(model, domain)

