# -*- coding: utf-8 -*-
from odoo import http

# class Myhotel(http.Controller):
#     @http.route('/myhotel/myhotel/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/myhotel/myhotel/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('myhotel.listing', {
#             'root': '/myhotel/myhotel',
#             'objects': http.request.env['myhotel.myhotel'].search([]),
#         })

#     @http.route('/myhotel/myhotel/objects/<model("myhotel.myhotel"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('myhotel.object', {
#             'object': obj
#         })