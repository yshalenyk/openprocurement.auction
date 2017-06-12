from zope import interface
from zope.interface import registry, implementedBy
from openprocurement.auction.interfaces import IComponents


@interface.implementer(IComponents)
class AuctionComponents(Components):

    def adapter(self, provides, adapts, name=""):
        """ TODO: create decorator for such thinks """
        
        if not isinstance(adapts, (tuple, list)):
            adapts = (adapts,)

        def wrapped(wrapper):
            
            self.registerAdapter(
                wrapper,
                adapts,
                provides,
                name=name
            )
            return wrapper

        return wrapped
        
    def component(self):
        """ TODO: use wraps decorator??
        """
        
        def wrapped(Wrapped):
            try:
                iface = list(implementedBy(Wrapped))[0]
            except IndexError:
                raise ValueError("{} should be marked as interface".format(Wrapped.__name__))
            name = Wrapped.__name__.lower()
            def new(cls, *args, **kw):
                ob = self.queryUtility(iface, name=name)
                if not ob:
                    ob = super(Wrapped, cls).__new__(*args, **kw)
                    self.regiterUtility(ob, iface, name=name)
                return ob
            Wrapped.__new__ = classmethod(new)
            return Wrapped

        return wrapped

    def q(self, iface, name='', default=''):
        """ TODO: query the component by 'iface' """    
        return self.queryUtility(iface, name=name, default=default)


components = AuctionComponents()

