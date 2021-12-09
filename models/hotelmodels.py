from odoo import models, fields, api, exceptions
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dt


class chambre(models.Model):

    _name = 'myhotel.chambre'

    room_id = fields.Integer()
    name = fields.Char(string="nom", required=True)
    categorie_id = fields.Many2one('myhotel.categorie', ondelete='cascade', string="Categorie", required=True)
    status = fields.Selection([('available', 'Disponible'), ('occupied', 'Occupée')], 'Statut', default='available')

    etage_id = fields.Many2one('myhotel.etage', ondelete='cascade', string="Etage", required=True)
    capacite = fields.Integer()
    room_reservation_line_ids = fields.One2many('hotel.room.reservation.line', 'room_id', string='Room Reserve Line')
    product_id = fields.Many2one('product.product', 'Product_id',required=True, delegate=True,
                                 ondelete='cascade')

    @api.onchange('isroom')
    def isroom_change(self):
        '''
        Based on isroom, status will be updated.
        '''
        if self.isroom is False:
            self.status = 'occupied'
        if self.isroom is True:
            self.status = 'available'

    @api.multi
    def write(self, vals):

        if 'isroom' in vals and vals['isroom'] is False:
            vals.update({'color': 2, 'status': 'occupied'})
        if 'isroom' in vals and vals['isroom'] is True:
            vals.update({'color': 5, 'status': 'available'})
        ret_val = super(chambre, self).write(vals)
        return ret_val


    @api.multi
    def set_room_status_occupied(self):
        """
        change the state to occupied of the hotel room.
        """
        return self.write({'isroom': False, 'color': 2})

    @api.multi
    def set_room_status_available(self):
        """
        change the state to available of the hotel room.
        """
        return self.write({'isroom': True, 'color': 5})

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(name)',
         "Le nom du chambre doit etre unique"),
    ]

    @api.model
    def cron_room_line(self):
        """
        This method is for scheduler
        every 1min scheduler will call this method and check Status of
        room is occupied or available
        --------------------------------------------------------------
        @param self: The object pointer
        @return: update status of hotel room reservation line
        """
        reservation_line_obj = self.env['hotel.room.reservation.line']
        now = datetime.now()
        curr_date = now.strftime(dt)
        for room in self.search([]):
            reserv_line_ids = [reservation_line.id for
                               reservation_line in
                               room.room_reservation_line_ids]
            reserv_args = [('id', 'in', reserv_line_ids),
                           ('check_in', '<=', curr_date),
                           ('check_out', '>=', curr_date)]
            reservation_line_ids = reservation_line_obj.search(reserv_args)
            status = {'isroom': True, 'color': 5}
            if reservation_line_ids.ids:
                status = {'isroom': False, 'color': 2}
            room.write(status)
            #if reservation_line_ids.ids:
                #raise exceptions.ValidationError('Verifiez le statut du chambre %s SVP!.' % (room.name))
        return True


    @api.constrains('capacite')
    def check_capacity(self):
        for r in self:
            if r.capacite <= 0:
                raise exceptions.ValidationError('La capacité du chambre doit etre superieur à 0')


class categorie(models.Model):
    _name = 'myhotel.categorie'

    name = fields.Char(string="nom", required=True)
    description = fields.Text()
    chambre_ids = fields.One2many('myhotel.chambre', 'categorie_id', string="Chambres")
    confort_ids = fields.Many2many('myhotel.confort', string="conforts")



class confort(models.Model):
    _name = 'myhotel.confort'

    name = fields.Char(string="conforts", required=True)


class etage(models.Model):
    _name = 'myhotel.etage'

    name = fields.Char(string="Etage", required=True)
    chambre_ids = fields.One2many('myhotel.chambre', 'etage_id', string="Chambres")


class service(models.Model):

    _name = 'myhotel.service'

    name = fields.Char(string="Nom de service", required=True)
    prix = fields.Integer()
    description = fields.Text()
    product_id = fields.Many2one('product.product', 'Product Category',
                                 required=True, delegate=True,
                                 ondelete='cascade')

class ProductProduct(models.Model):

    _inherit = "product.product"


    isroom = fields.Boolean('Is Room')
    iscategid = fields.Boolean('Is Categ')
    isservice = fields.Boolean('Is Service')


