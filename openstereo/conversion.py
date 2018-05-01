#Not tremendously stupid converter for orientation data. As of now,
#hopefully will be able to convert from strike/dip+dipquadrant, whether
#the strike is in azimuth or quadrant notation.
#We can but hope.
#Ver 0.5.0
import re

from collections import defaultdict

attitude_parser = re.compile("([NSEW]{0,2})(\d*)([NSEW]{0,2})[^NSEW0-9](\d+)([NSEW]{0,2})", re.IGNORECASE)
azimuth_parser = re.compile("([NSEW]{0,2})(\d*)([NSEW]{0,2})", re.IGNORECASE)
dip_parser = re.compile("(\d+)([NSEW]{0,2})", re.IGNORECASE)


def parse_quadrant(leading, number, trailing):
    base, multiplier = quadrants[(leading, trailing)]
    return base + number*multiplier

def parse_strike_quadrant(strike, dip_quadrant):
    return strike + dip_quadrants[((strike%180)//90, trends[dip_quadrant//90])]

p = re.compile('(N?)(\d*)([EW ]?).*', re.IGNORECASE)
class Attitude(object):
    """Class to transcode attitude data"""
    #Dispatcher truth table. There oughta be an eleganter way to do this, though.
    strike_coding = {(True, True, True): 'quadrant',
                     (True, True, False): 'azimuth',
                     (True, False, True): 'cardinal',
                     (True, False, False): 'cardinal',
                     (False, True, True): 'dip',
                     (False, True, False): 'azimuth',
                     (False, False, False): 'error',
                     (False, False, True): 'error'}

    #Constants for trike processing for quadrants. Maybe should reposition this.
    strike_leading = {'N': 0, 'S': 180}
    strike_trailing = {'E': 1, 'W': -1}
    strike__leading_multiplier = {'N': 1, 'S': -1}
    #quads = {"NE":-90,
    #       "SE":90,
    #       "SW":90,
    #       "NW":-90}
    #Constants for conversion based on dip, with a default value
    quadrants = defaultdict(lambda: 90)
    quadrants.update({"NE":-90, 
                      "SE":90,  
                      "SW":90,
                      "NW":-90})

    #are regex matches fast? They seem to be...                             
    strike_pattern = re.compile('([NS]?)([+-0-9.e]*)([EW ]?).*', re.IGNORECASE) #Regex parser for strike, separating the constituent letters and numbers
    dip_pattern = re.compile('([+-0-9.e]*)([NESW]*).*', re.IGNORECASE) #Regex parser for dip, separating the dip from the dip direction quadrant, if present
    
    def process_data(self, attitude, dd=True):
        self.data = []
        dd = (dd and 90.0) or 0.0
        for strike, dip in attitude:
            #print strike, dip
            #Dispatch the strike and dip combination to the correct parsing function.
            strike, dip = strike.upper(), dip.upper()
            dip_direction, dip = self.process_strikedip(strike, dip)
            dip_direction = (dip_direction - dd) % 360
            self.data.append((dip_direction, dip))
        return self.data

    def do_quadrant(self, strike, dip):
        dip, dip_direction_quadrant = Attitude.dip_pattern.match(dip).groups()
        if not dip:
            return 'err', 'err'
#       elif not dip_direction_quadrant:
#           return ((Attitude.strike_leading[self.leading_letter.upper()] + Attitude.strike_trailing[self.trailing_letter.upper()]*strike__leading_multiplier[self.leading_letter.upper()]*int(self.number)) % 360 + 90) % 360, int(dip)
        return ((Attitude.strike_leading[self.leading_letter] + Attitude.strike_trailing[self.trailing_letter]*Attitude.strike__leading_multiplier[self.leading_letter]*float(self.number)) % 360 + Attitude.quadrants[dip_direction_quadrant]) % 360, float(dip)
        #pass

    def do_azimuth(self, strike, dip):
        try:
            dip = float(dip)
            dip_direction_quadrant = ""
        except ValueError:
            dip, dip_direction_quadrant = Attitude.dip_pattern.match(dip).groups()
            if not dip:
                return 'err', 'err'
        return (float(self.number) + Attitude.quadrants[dip_direction_quadrant]) % 360, float(dip)
        #pass

    def do_cardinal(self, strike, dip):
        dip, dip_direction_quadrant = Attitude.dip_pattern.match(dip).groups()
        return (Attitude.strike_leading[self.leading_letter] - Attitude.strike_trailing[dip_direction_quadrant]*90) % 360.0, dip
        #pass

    def do_dip(self, dip, strike):
        #had to do somewhat of a hack... Better way, anyone?
        if reduce(lambda x, y: bool(x and y), Attitude.strike_pattern.match(strike).groups()): #So as to prevent an infinite recursion, there might be a better way to do this.
            return self.process_strikedip(strike, dip)
        else:
            return 'err', 'err'

    def do_error(self, strike, dip):
        return 'err', 'err'

    def process_strikedip(self, strike, dip):
        try:
            float(strike)
            self.number = strike
            coding = 'azimuth'
            self.leading_letter, self.trailing_letter = '', ''
        except ValueError:
            self.leading_letter, self.number, self.trailing_letter = Attitude.strike_pattern.match(strike).groups()
            coding = Attitude.strike_coding[(bool(self.leading_letter), bool(self.number), bool(self.trailing_letter))]
        #print strike, dip
        #Dispatch the strike and dip combination to the correct parsing function.
        #if __debug__: print strike.upper(), dip.upper()
        return getattr(self, "do_%s" % coding)(strike, dip)
