import json
import logging
import requests
from odoo import  http, api, fields, models, _
from odoo.exceptions import ValidationError
from gtts import gTTS
import base64
import os

_logger = logging.getLogger(__name__)


class KsDashboardNInjaAI(models.TransientModel):
    _name = 'ks_dashboard_ninja.arti_int'
    _description = 'AI Dashboard'

    ks_type = fields.Selection([('ks_model', 'Model'), ('ks_keyword', 'Keywords')],
                               string="Ks AI Type", default='ks_model')

    ks_import_model_id = fields.Many2one('ir.model', string='Model ID',
                                  domain="[('access_ids','!=',False),('transient','=',False),"
                                         "('model','not ilike','base_import%'),'|',('model','not ilike','ir.%'),('model','=ilike','_%ir.%'),"
                                         "('model','not ilike','web_editor.%'),('model','not ilike','web_tour.%'),"
                                         "('model','!=','mail.thread'),('model','not ilike','ks_dash%'),('model','not ilike','ks_to%')]",
                                  help="Data source to fetch and read the data for the creation of dashboard items. ")

    ks_import_model = fields.Many2one('ir.model', string='Model',
                                         domain="[('access_ids','!=',False),('transient','=',False),"
                                                "('model','not ilike','base_import%'),('model','not ilike','ir.%'),"
                                                "('model','not ilike','web_editor.%'),('model','not ilike','web_tour.%'),"
                                                "('model','!=','mail.thread'),('model','not ilike','ks_dash%'),('model','not ilike','ks_to%')]",
                                         help="Data source to fetch and read the data for the creation of dashboard items. ")
    ks_input_keywords = fields.Char("Ks Keywords")
    ks_model_show = fields.Boolean(default = False, compute='_compute_show_model')

    @api.onchange('ks_input_keywords')
    def _compute_show_model(self):
        if self.ks_input_keywords and self.ks_type=="ks_keyword":
            api_key = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.dn_api_key')
            url = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.url')
            if api_key and url:
                json_data = {'name': api_key,
                             'type': self.ks_type,
                             'keyword': self.ks_input_keywords
                             }
                url = url + "/api/v1/ks_dn_keyword_gen"
                ks_response = requests.post(url, data=json_data)
                if json.loads(ks_response.text) == False:
                    self.ks_model_show = True
                else:
                    self.ks_model_show = False
        else:
            self.ks_model_show = False

    @api.model
    def ks_get_keywords(self):
        url = self.env['ir.config_parameter'].sudo().get_param(
            'ks_dashboard_ninja.url')
        if url:
            url = url + "/api/v1/ks_dn_get_keyword"
            ks_response = requests.post(url)
            if ks_response.status_code == 200:
                return json.loads(ks_response.text)
            else:
                return []



    def ks_do_action(self):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json",
                   "Catch-Control": "no-cache",
                   }

        if self.ks_import_model_id:
            ks_model_name = self.ks_import_model_id.model
            ks_fields = self.env[ks_model_name].fields_get()
            ks_filtered_fields = {key: val for key, val in ks_fields.items() if val['type'] not in ['many2many', 'one2many', 'binary'] and val['name'] != 'id' and val['name'] != 'sequence' and val['store'] == True}
            ks_fields_name = {val['name']:val['type'] for val in ks_filtered_fields.values()}
            question = ("columns: "+ f"{ks_fields_name}")

            api_key = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.dn_api_key')
            url = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.url')
            if api_key and url:
                json_data = {'name': api_key,
                        'question':question,
                        'type': self.ks_type,
                        'url': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                        'db_name': self.env.cr.dbname
                        }
                url = url+"/api/v1/ks_dn_main_api"
                ks_ai_response = requests.post(url, data=json_data)
                if ks_ai_response.status_code == 200:
                    ks_ai_response = json.loads(ks_ai_response.text)
                    # create dummy dash to create items on the dashboard, later deleted it.
                    ks_create_record = self.env['ks_dashboard_ninja.board'].create({
                        'name': 'AI dashboard',
                        'ks_dashboard_menu_name': 'AI menu',
                        'ks_dashboard_default_template': self.env.ref('ks_dashboard_ninja.ks_blank', False).id,
                        'ks_dashboard_top_menu_id': self.env['ir.ui.menu'].search([('name', '=', 'My Dashboard')])[0].id,
                    })
                    ks_dash_id = ks_create_record.id

                    ks_result = self.env['ks_dashboard_ninja.item'].create_ai_dash(ks_ai_response, ks_dash_id,
                                                                                   ks_model_name)
                    context = {'ks_dash_id': self._context['ks_dashboard_id'],
                               'ks_dash_name': self.env['ks_dashboard_ninja.board'].search([
                                   ('id','=',self._context['ks_dashboard_id'])]).name,'ks_delete_dash_id':ks_dash_id }

                    # return client action created through js for AI dashboard to render items on dummy dashboard
                    if (ks_result == "success"):
                        return {
                            'type': 'ir.actions.client',
                            'name': 'AI Dashboard',
                            'params': {'ks_dashboard_id': ks_create_record.id},
                            'tag': 'ks_ai_dashboard_ninja',
                            'context': context,
                            'target':'new'
                        }
                    else:
                        self.env['ks_dashboard_ninja.board'].browse(ks_dash_id).unlink()
                        raise ValidationError(_("Items didn't render because AI provides invalid response for this model.Please try again"))
                else:
                    raise ValidationError(_("AI Responds with the following status:- %s") % ks_ai_response.text)
            else:
                raise ValidationError(_("Please enter URL and API Key in General Settings"))
        else:
            raise ValidationError(_("Please enter the Model"))



    def ks_generate_item(self):
            if self.ks_input_keywords:
                api_key = self.env['ir.config_parameter'].sudo().get_param(
                    'ks_dashboard_ninja.dn_api_key')
                url = self.env['ir.config_parameter'].sudo().get_param(
                    'ks_dashboard_ninja.url')
                if api_key and url:
                    json_data = {'name': api_key,
                                 'type': self.ks_type,
                                 'keyword':self.ks_input_keywords
                                 }
                    url = url + "/api/v1/ks_dn_keyword_gen"
                    ks_response = requests.post(url, data=json_data)
                else:
                    raise ValidationError(_("Please put API key and URL"))
                if  json.loads(ks_response.text) != False and ks_response.status_code==200 :
                    ks_ai_response = json.loads(ks_response.text)
                    ks_dash_id = self._context['ks_dashboard_id']
                    ks_model_name = ks_ai_response[0]['model']
                    ks_result = self.env['ks_dashboard_ninja.item'].create_ai_dash(ks_ai_response, ks_dash_id,
                                                                               ks_model_name)
                    if ks_result == "success":
                        return{
                        'type': 'ir.actions.client',
                        'tag': 'reload',
                        }
                    else:
                        raise ValidationError(_("Items didn't render, please try again!"))
                else:
                    ks_model_name = self.ks_import_model.model
                    ks_fields = self.env[ks_model_name].fields_get()
                    ks_filtered_fields = {key: val for key, val in ks_fields.items() if
                                          val['type'] not in ['many2many', 'one2many', 'binary'] and val[
                                              'name'] != 'id' and val['name'] != 'sequence' and val['store'] == True}
                    ks_fields_name = {val['name']: val['type'] for val in ks_filtered_fields.values()}
                    question = ("schema: " + f"{ks_fields_name}")
                    model =("model:" + f"{ks_model_name}")
                    api_key = self.env['ir.config_parameter'].sudo().get_param(
                        'ks_dashboard_ninja.dn_api_key')
                    url = self.env['ir.config_parameter'].sudo().get_param(
                        'ks_dashboard_ninja.url')
                    if api_key and url:
                        json_data = {'name': api_key,
                                     'question': self.ks_input_keywords,
                                     'type':self.ks_type,
                                     'schema':question,
                                     'model':model,
                                     'url': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                                     'db_name': self.env.cr.dbname
                                     }
                        url = url + "/api/v1/ks_dn_main_api"
                        ks_ai_response = requests.post(url, data=json_data)
                        if ks_ai_response.status_code == 200:
                            ks_ai_response = json.loads(ks_ai_response.text)
                            ks_dash_id = self._context['ks_dashboard_id']
                            ks_model_name = (ks_ai_response[0]['model']).lower()
                            if self.env['ir.model'].search([('model','=',ks_model_name)]).id or self.env['ir.model'].search([('name','=',ks_model_name)]).id:
                                if self.env['ir.model'].search([('name','=',ks_model_name)]).id:
                                    ks_model_name = self.env['ir.model'].search([('name','=',ks_model_name)]).model
                                else:
                                    ks_model_name = (ks_ai_response[0]['model']).lower()
                                ks_result = self.env['ks_dashboard_ninja.item'].create_ai_dash(ks_ai_response, ks_dash_id,ks_model_name)
                                if ks_result == "success":
                                    return {
                                        'type': 'ir.actions.client',
                                        'tag': 'reload',
                                    }
                                else:
                                    raise ValidationError(_("Items didn't render, please try again!"))
                            else:
                                raise ValidationError(_("%s model does not exist.Please install")% ks_model_name)
                        else:
                            raise ValidationError(
                                _("AI Responds with the following status:- %s") % ks_ai_response.text)

                    else:
                        raise ValidationError(_("Please enter URL and API Key in General Settings"))
            else:
                raise ValidationError(_("Enter the input keywords to render the item"))

    @api.model
    def ks_generate_analysis(self,ks_items_explain,ks_rest_items,dashboard_id):
        if ks_items_explain:
            result = []
            api_key = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.dn_api_key')
            ks_url = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.url')
            words = self.env['ir.config_parameter'].sudo().get_param(
                'ks_dashboard_ninja.ks_analysis_word_length')
            url = ks_url + "/api/v1/ks_dn_main_api"
            for i in range(0,len(ks_items_explain)):
                if api_key and url :
                    json_data = {'name': api_key,
                                 'items':json.dumps(ks_items_explain[i]),
                                 'type':'ks_ai_explain',
                                 'url': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                                 'db_name': self.env.cr.dbname,
                                 'words':  words if words else 100
                                 }
                    ks_response = requests.post(url, data=json_data)
                    if ks_response.status_code == 200 and json.loads(ks_response.text):
                        ks_ai_response = json.loads(ks_response.text)
                        item = ks_ai_response[0]
                        if item['analysis'] and item['insights']:
                            try:
                                self.env['ks_dashboard_ninja.item'].browse(item['id']).write({
                                'ks_ai_analysis': item['analysis']+'ks_gap'+item['insights']
                                })
                                result.append(True)
                            except:
                                result
                        else:
                            result

                    else:
                        result
                else:
                    raise ValidationError(_("Please put API key and URL"))
            if len(result):
                self.env['ks_dashboard_ninja.board'].browse(dashboard_id).write({
                    'ks_ai_explain_dash': True
                })
                return True
            else:
                raise ValidationError(_("AI Responds with the wrong analysis. Please try again "))
        elif ks_rest_items:
            self.env['ks_dashboard_ninja.board'].browse(dashboard_id).write({
                'ks_ai_explain_dash': True
            })
            return True
        else:
            return False

    @api.model
    def ks_switch_default_dashboard(self,dashboard_id):
        self.env['ks_dashboard_ninja.board'].browse(dashboard_id).write({
            'ks_ai_explain_dash':False
        })
        return True
    @api.model
    def ks_generatetext_to_speech(self,item_id):
        if (item_id):
            try:
                ks_text = self.env['ks_dashboard_ninja.item'].browse(item_id).ks_ai_analysis
                if ks_text:
                    language = 'en'
                    ks_myobj = gTTS(text=ks_text, lang=language, slow=False)
                    ks_file = ks_myobj.save('ks_audio.mp3')
                    with open('ks_audio.mp3', 'rb') as audio_file:
                        binary_data = audio_file.read()
                        wav_file = base64.b64encode( binary_data).decode('UTF-8')
                    data = {"snd": wav_file}
                    return json.dumps(data)
                else:
                    return False
            except Exception as e:
                print(e)
                raise ValidationError(_("Some problem in audio generation."))

        else:
            return False

