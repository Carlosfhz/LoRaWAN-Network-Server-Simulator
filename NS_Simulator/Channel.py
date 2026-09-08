import math

class Channel:


    def __init__(self,PL_seleciton="log",seed=None):
        self.PATH_LOSS_EXPONENT = 2.75
        self.PL0 = 74.85  # in dB
        self.D0 = 1.0     # in m
        self.SHADOWING_STD = 1.0
        self.PL_selection = PL_seleciton
        self.seed = seed

    def get_path_loss(self, random_gen, distance,tx_power):
        if self.PL_selection == "log":
            return tx_power - self.get_path_loss_log(random_gen, distance)
        elif self.PL_selection == "okumura":
            rx_after_okumura = tx_power - self.get_path_loss_okumura(distance)
            PL_final = self.get_nakagami_fading(random_gen,rx_after_okumura,distance) 
            #print(f"Tx power: {tx_power:.2f} dBm, Distance: {distance:.2f} m, Path Loss (Okumura): {self.get_path_loss_okumura(distance):.2f} dB, Received Power after Okumura: {rx_after_okumura:.2f} dBm, Final Received Power with Nakagami fading: {PL_final:.2f} dBm")
            return PL_final
        else:
            raise ValueError("Invalid path loss selection. Choose 'log' or 'okumura'.")
    def get_path_loss_log(self, random_gen, distance):
        """
        Calculate path loss using the Urban model with censored data
        PL(d) = PL(d0) + 10*gamma*log10(d/d0) + x_sigma
        """
        # Large Scale Fading (LSF)
        LSF = self.PL0 + 10 * self.PATH_LOSS_EXPONENT * math.log10(distance / self.D0)
    
        #print(f"[LSF={LSF:.2f} dB] ", end="")
        # Shadow Fading (ShF) - Normal distribution
        ShF = self._next_gaussian(random_gen) * self.SHADOWING_STD
        #print(f"[ShF={ShF:.2f} dB] ", end="")
        
        # Small Scale Fading (SSF) - Exponential distribution
        SSF = math.log(1 - random_gen.random()) / (-1.0)
        #print(f"[SSF={SSF:.2f} dB] ", end="")
        
        return LSF + ShF + SSF

    def get_path_loss_okumura(self, distance):
        """
        Calculate path loss using the Okumura-Hata model
        PL(d) = 69.55 + 26.16*log10(f) - 13.82*log10(hb) - a(hm) + (44.9 - 6.55*log10(hb))*log10(d)
        For simplicity, we will use fixed values for frequency (f), base station height (hb), and mobile station height (hm).
        """
        f = 868100000.0  # Frequency in MHz
        hb = 30  # Base station height in meters
        hm = 1.5 # Mobile station height in meters

        # Calculate the correction factor a(hm)
        if f <= 200:
            a_hm = (1.1 * math.log10(f) - 0.7) * hm - (1.56 * math.log10(f) - 0.8)
        else:
            a_hm = (1.1 * math.log10(f) - 0.7) * hm - (1.56 * math.log10(f) - 0.8)

        PL_urban = (69.55 + 26.16 * math.log10(f) - 13.82 * math.log10(hb) - a_hm +
              (44.9 - 6.55 * math.log10(hb)) * math.log10(distance))
        
        PL_open = PL_urban - 4.78 * (math.log10(f))**2 + 18.33 * math.log10(f) - 40.94
        
        
        return PL_open
    def get_nakagami_m(self, distance):
        """
        Calculate the Nakagami-m fading parameter based on distance.
        Uses a three-region model similar to NS-3's NakagamiPropagationLossModel.
        
        Args:
            distance: Distance in meters
            
        Returns:
            Nakagami m parameter for the given distance
        """
        distance1 = 80.0   # First distance threshold (m)
        distance2 = 200.0  # Second distance threshold (m)
        
        m0 = 1   # m parameter for distances < distance1
        m1 = 1  # m parameter for distance1 <= distances < distance2
        m2 = 1  # m parameter for distances >= distance2
        
        if distance < distance1:
            return m0
        elif distance < distance2:
            return m1
        else:
            return m2

    def get_nakagami_fading(self, random_gen, tx_power_dbm, distance):
        """
        Calculate received power using Nakagami fading model.
        
        Args:
            random_gen: Random number generator
            tx_power_dbm: Transmitted power in dBm
            distance: Distance in meters
            
        Returns:
            Received power in dBm
        """
        m = self.get_nakagami_m(distance)
        
        # Convert from dBm to Watts
        power_w = 10 ** ((tx_power_dbm - 30) / 10)
        
        # Apply Nakagami fading using Gamma distribution
        int_m = int(m)
        if int_m == m:
            # Use Erlang distribution for integer m
            result_power_w = random_gen.gammavariate(int_m, power_w / m)
        else:
            # Use Gamma distribution for non-integer m
            result_power_w = random_gen.gammavariate(m, power_w / m)
        
        # Convert back to dBm
        result_power_dbm = 10 * math.log10(result_power_w) + 30
        
        return result_power_dbm

    @staticmethod
    def get_distance(node1, node2):
        """Calculate distance between two nodes"""
        return Channel.get_distance_coords(node1[0], node1[1], 
                                         node2[0], node2[1])

    @staticmethod
    def get_distance_coords(x1, y1, x2, y2):
        """Calculate Euclidean distance between two points"""
        delta_x = x2 - x1
        delta_y = y2 - y1
        return float(math.sqrt(delta_x * delta_x + delta_y * delta_y))

    def _next_gaussian(self, random_gen):
        """Generate Gaussian random number using Marsaglia method"""
        if self.seed is not None:
            random_gen.seed(self.seed)
        while True:
            v1 = 2.0 * random_gen.random() - 1.0
            v2 = 2.0 * random_gen.random() - 1.0
            s = v1 * v1 + v2 * v2
            if s < 1.0 and s != 0.0:
                break
        
        s = math.sqrt((-2.0 * math.log(s)) / s)
        return v1 * s
