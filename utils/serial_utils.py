# coding=UTF-8

"""
@time: 2017/11/3 11:02
串口通信封装方法
"""
import datetime
import traceback

import logging

import time

import serial

logger = logging.getLogger(__name__)

BAUD_RATE = 115200


class OrderCode:
    Status = 0xC0
    LoadConf = 0xC1
    Control = 0xC2


class Status:
    IDLE = 1
    BUSY = 2
    FIXING = 3
    ERROR = 4


def get_validate_num(send_data: list):
    """
    取最后2位，对0xFF取余数
    :param send_data:
    :return:
    """
    return sum(send_data) % 256


def int_to_bytes(data: list):
    """
    :param data: [255, 85, 192, 0, 0, 0, 0, 0, 0, 0, 0, 20]
    :return: b'\xffU\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x14'
    """
    return bytes(data)


def bytes_to_int(data: list):
    """
    :param data: b'\xffU\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x14'
    :return:[255, 85, 192, 0, 0, 0, 0, 0, 0, 0, 0, 20]
    """
    return [int(x) for x in data]


def prefix_send_data(order: int, send_data: list):
    """
    将发送数据处理为直接和主板通信的十六进制数据
    上位机下发数据帧格式  固定为12 BYTE，校验为前面所有字节的累加和（超过2位取最后2位，0x123->0x23）
    帧头	帧头	命令	参数1	参数2	参数3	参数4	参数5	参数6	参数7	参数8	检验
    0xFF	0x55	0xCx
    :param order:
    :param send_data: [100, 100, 100, 100, 100, 100, 100, 100] 8位十进制列表
    :return:
    """
    send_data = [0xff, 0x55, order] + send_data
    validate_num = get_validate_num(send_data)
    send_data.append(validate_num)
    return int_to_bytes(send_data)


def prefix_receive_data(receive_data: list):
    """
    将从主板接收到的字节数据处理为十进制数据
    下位机回应数据帧格式  固定为6 BYTE，校验为前面所有字节的累加和（超过2位取最后2位，0x123->0x23）
    帧头	帧头	命令	参数1	参数2	检验
    0xFF	0x55	0xCx
    :param receive_data: b'\xffU\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x14'
    :return:
    """
    receive_data = bytes_to_int(receive_data)
    assert get_validate_num(receive_data[:-1]) == receive_data[-1], "接受数据校验不通过"
    return receive_data[3: 5]


def serial_actiong(ser: serial.Serial, send_data):
    """操作硬件接口"""
    ser.write(send_data)
    receive_data = ser.read(6)
    return prefix_receive_data(receive_data)


def get_status_and_gift_num(ser: serial.Serial):
    """
    获取机器信息
    :param ser:
    :return: status, gift_num
    """
    try:
        send_data = [0, 0, 0, 0, 0, 0, 0, 0]
        send_data = prefix_send_data(OrderCode.Status, send_data)
        status, gift_num = serial_actiong(ser, send_data)
        return status, gift_num
    except serial.SerialTimeoutException as e:
        logger.error(e)
    except Exception as e:
        logging.error(e)
        logger.error(traceback.format_exc(e))


def get_status_and_gift_num_with_open_and_close(port):
    ser = serial.Serial(port, baudrate=BAUD_RATE, timeout=1)
    if not ser.isOpen():
        ser.open()
    rs = get_status_and_gift_num(ser)
    ser.close()
    return rs


def load_conf(ser, game_time=30, small_power=15, big_power=60, catch=False):
    """加载参数到主板"""
    try:
        if catch:
            send_data = [100, 100, 100, 100, 100, 100, game_time, 0]
        else:
            send_data = [100, 100, 100, small_power, big_power, 100, game_time, 0]
        send_data = prefix_send_data(OrderCode.LoadConf, send_data)
        succeed, nothing = serial_actiong(ser, send_data)
        return succeed, nothing
    except serial.SerialTimeoutException as e:
        logger.error(e)
    except Exception as e:
        logging.error(e)
        logger.error(traceback.format_exc(e))


def load_conf_with_open_and_close(port, game_time=30, small_power=15, big_power=60, catch=False):
    ser = serial.Serial(port, baudrate=BAUD_RATE, timeout=1)
    if not ser.isOpen():
        ser.open()
    rs = load_conf(ser, game_time, small_power, big_power, catch)
    ser.close()
    return rs


class Command:
    FORWARD = 1
    BACK = 2
    LEFT = 3
    RIGHT = 4
    CATCH = 5


def get_negative(number):
    """转换为符号位负数"""
    # 因为第一位为符号位
    return 255 - number


def control(ser: serial.Serial, command, move_time):
    """
    代替摇杆操作天车
    :param ser:
    :param command: 方向（正对机器视角）
    :param move_time: 移动时间(10为1秒，大概)
    :return:
    """
    try:
        if command == Command.FORWARD:
            send_data = [move_time, 0, 0, 0, 0, 0, 0, 0]
        elif command == Command.BACK:
            send_data = [get_negative(move_time), 0, 0, 0, 0, 0, 0, 0]
        elif command == Command.LEFT:
            send_data = [0, move_time, 0, 0, 0, 0, 0, 0]
        elif command == Command.RIGHT:
            send_data = [0, get_negative(move_time), 0, 0, 0, 0, 0, 0]
        elif command == Command.CATCH:
            send_data = [0, 0, 1, 0, 0, 0, 0, 0]
        else:
            raise Exception("error command value: %s" % command)
        send_data = prefix_send_data(OrderCode.Control, send_data)
        succeed, nothing = serial_actiong(ser, send_data)
        return succeed, nothing
    except serial.SerialTimeoutException as e:
        logger.error(e)
    except Exception as e:
        logging.error(e)
        logger.error(traceback.format_exc(e))


def control_with_open_and_close(port, command, move_time):
    """
    代替摇杆操作天车并自动处理串口打开和关闭
    :param port:
    :param command:
    :param move_time:
    :return:
    """
    ser = serial.Serial(port, baudrate=BAUD_RATE, timeout=1)
    if not ser.isOpen():
        ser.open()
    rs = control(ser, command, move_time)
    ser.close()
    return rs


def init_serial(port):
    serial.Serial(port, baudrate=BAUD_RATE, timeout=1)


def main():
    port = "COM3"
    ser = serial.Serial(port, baudrate=BAUD_RATE, timeout=1)
    print(get_status_and_gift_num(ser))
    print(load_conf(ser, 5, True))
    # for i in range(256):
    #     time.sleep(0.01)
    #     print(control(ser, Command.LEFT, i))
    print(control(ser, Command.LEFT, 15))
    time.sleep(2)
    print(control(ser, Command.RIGHT, 5))
    time.sleep(10)
    print(get_status_and_gift_num(ser))


if __name__ == '__main__':
    main()
