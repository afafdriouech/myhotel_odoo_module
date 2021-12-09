from odoo import models, fields, api, exceptions

class client(models.Model):

    _inherit = 'res.partner'

    # Add a new column to the res.partner

    reservation_ids = fields.One2many('myhotel.reservation', 'client_id', string="Mes reservations", readonly=True)


class reclamation(models.Model):

    _name = 'myhotel.reclamation'


    name = fields.Char()
