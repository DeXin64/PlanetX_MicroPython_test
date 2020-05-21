from microbit import *
import time

DEGREES = u'\xb0'

J1 = pin1
J2 = pin2
J3 = pin13
J4 = pin15


class DataError(Exception):
    pass


def _calc_bytes(pull_up_lengths):

    shortest = 1000
    longest = 0

    for i in range(0, len(pull_up_lengths)):
        length = pull_up_lengths[i]
        if length < shortest:
            shortest = length
        if length > longest:
            longest = length

    halfway = shortest + (longest - shortest) / 2
    data = bytearray(5)
    did = 0
    byte = 0

    for i in range(len(pull_up_lengths)):
        byte = byte << 1

        if pull_up_lengths[i] > halfway:
            byte = byte | 1

        if (i + 1) % 8 == 0:
            data[did] = byte
            did += 1
            byte = 0

    return data


def _calc_checksum(data):
    return data[0] + data[1] + data[2] + data[3] & 0xff


def _parse_data(buffer_):
    # changed initial states, tyey are lost in the change over
    INIT_PULL_DOWN = 1
    INIT_PULL_UP = 2
    DATA_1_PULL_DOWN = 3
    DATA_PULL_UP = 4
    DATA_PULL_DOWN = 5

    # state = INIT_PULL_DOWN
    state = INIT_PULL_UP

    max_bits = 50
    bits = bytearray(max_bits)
    length = 0
    bit_ = 0

    for i in range(len(buffer_)):

        current = buffer_[i]
        length += 1

        if state == INIT_PULL_DOWN:
            if current == 0:
                state = INIT_PULL_UP
                continue
            else:
                continue
        if state == INIT_PULL_UP:
            if current == 1:
                state = DATA_1_PULL_DOWN
                continue
            else:
                continue
        if state == DATA_1_PULL_DOWN:
            if current == 0:
                state = DATA_PULL_UP
                continue
            else:
                continue
        if state == DATA_PULL_UP:
            if current == 1:
                length = 0
                state = DATA_PULL_DOWN
                continue
            else:
                continue
        if state == DATA_PULL_DOWN:
            if current == 0:
                bits[bit_] = length
                bit_ += 1
                state = DATA_PULL_UP
                continue
            else:
                continue

        if bit_ >= max_bits:
            break

    if bit_ == 0:
        return None

    results = bytearray(bit_)
    for i in range(bit_):
        results[i] = bits[i]
    return results


class DHT11:
    """基本描述

    DHT11温湿度传感器

    """
    def __init__(self, RJ_pin):
        if RJ_pin == J1:
            self.__pin = pin8
        elif RJ_pin == J2:
            self.__pin = pin12
        elif RJ_pin == J3:
            self.__pin = pin14
        elif RJ_pin == J4:
            self.__pin = pin16

    def get_value(self):
        """

        读取当前温湿度，两次请求必须间隔超过2s以上

        Returns:
            temp, humid 两个返回值温度和湿度，列表返回，读取可用[0][1]
        """
        # creating these locals speeds things up len() is very slow
        pin = self.__pin
        pin2bit = self._pin2bit()
        buffer_ = bytearray(320)
        length = (len(buffer_) // 4) * 4

        for i in range(length, len(buffer_)):
            buffer_[i] = 1

        pin.write_digital(1)
        time.sleep_ms(50)
        self._block_irq()

        pin.write_digital(0)
        time.sleep_ms(20)

        pin.set_pull(pin.PULL_UP)

        if self._grab_bits(pin2bit, buffer_, length) != length:
            self._unblock_irq()
            raise Exception("Grab bits failed.")
        else:
            self._unblock_irq()

        # for b in buffer_:
        #    print(b, end = "")
        # print('')

        data = _parse_data(buffer_)

        del buffer_

        if data is None or len(data) != 40:
            if data is None:
                bits = 0
            else:
                bits = len(data)
            raise DataError("Too many or too few bits " + str(bits))

        data = _calc_bytes(data)

        checksum = _calc_checksum(data)
        if data[4] != checksum:
            raise DataError("Checksum invalid.")

        temp = data[2] + (data[3] / 10)
        humid = data[0] + (data[1] / 10)
        return temp, humid

    def _pin2bit(self):
        # this is a dictionary, microbit.pinX can't be a __hash__
        pin = self.__pin
        if pin == pin0:
            shift = 3
        elif pin == pin1:
            shift = 2
        elif pin == pin2:
            shift = 1
        elif pin == pin3:
            shift = 4
        elif pin == pin4:
            shift = 5
        elif pin == pin6:
            shift = 12
        elif pin == pin7:
            shift = 11
        elif pin == pin8:
            shift = 18
        elif pin == pin9:
            shift = 10
        elif pin == pin10:
            shift = 6
        elif pin == pin12:
            shift = 20
        elif pin == pin13:
            shift = 23
        elif pin == pin14:
            shift = 22
        elif pin == pin15:
            shift = 21
        elif pin == pin16:
            shift = 16
        else:
            raise ValueError('function not suitable for this pin')

        return shift

    @staticmethod
    @micropython.asm_thumb
    def _block_irq():
        cpsid('i')  # disable interrupts to go really fast

    @staticmethod
    @micropython.asm_thumb
    def _unblock_irq():
        cpsie('i')  # enable interupts nolonger time critical

    # r0 - pin bit id
    # r1 - byte array
    # r2 - len byte array, must be a multiple of 4
    @staticmethod
    @micropython.asm_thumb
    def _grab_bits(r0, r1, r2):
        b(START)

        # DELAY routine
        label(DELAY)
        mov(r7, 0x2d)
        label(delay_loop)
        sub(r7, 1)
        bne(delay_loop)
        bx(lr)

        label(READ_PIN)
        mov(r3, 0x50)  # r3=0x50
        lsl(r3, r3, 16)  # r3=0x500000
        add(r3, 0x05)  # r3=0x500005
        lsl(r3, r3, 8)  # r3=0x50000500 -- this points to GPIO registers
        add(r3, 0x10)  # r3=0x50000510 -- points to read_digital bits
        ldr(r4, [r3, 0])  # move memory@r3 to r2
        mov(r3, 0x01)  # create bit mask in r3
        lsl(r3, r0)  # select bit from r0
        and_(r4, r3)
        lsr(r4, r0)
        bx(lr)

        label(START)
        mov(r5, 0x00)  # r5 - byte array index
        label(again)
        mov(r6, 0x00)  # r6 - current word
        bl(READ_PIN)
        orr(r6, r4)  # bitwise or the pin into current word
        bl(DELAY)
        bl(READ_PIN)
        lsl(r4, r4, 8)  # move it left 1 byte
        orr(r6, r4)  # bitwise or the pin into current word
        bl(DELAY)
        bl(READ_PIN)
        lsl(r4, r4, 16)  # move it left 2 bytes
        orr(r6, r4)  # bitwise or the pin into current word
        bl(DELAY)
        bl(READ_PIN)
        lsl(r4, r4, 24)  # move it left 3 bytes
        orr(r6, r4)  # bitwise or the pin into current word
        bl(DELAY)

        add(r1, r1, r5)  # add the index to the bytearra addres
        str(r6, [r1, 0])  # now 4 have been read store it
        sub(r1, r1, r5)  # reset the address
        add(r5, r5, 4)  # increase array index
        sub(r4, r2, r5)  # r4 - is now beig used to count bytes written
        bne(again)

        label(RETURN)
        mov(r0, r5)  # return number of bytes written


if __name__ == '__main__':

    sensor = DHT11(J1)
    while True:
        t, h = sensor.get_value()
        print("%2.1f%sC  %2.1f%% " % (t, DEGREES, h))
        time.sleep(2)