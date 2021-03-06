#!/usr/bin/env python
#[Packet Generator]-->[BPSK Modulator]-->[Frequency Hopping Module]-->[USRP Sink]
# Copyright 2014 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

"""
TXs a waveform (either from a file, or a sinusoid) in a frequency-hopping manner.
"""

import time
import numpy
import argparse
import pmt
from gnuradio import gr
from gnuradio import blocks
from gnuradio import uhd

from gnuradio import digital
from gnuradio import eng_notation
from gnuradio import filter
from gnuradio import gr
from gnuradio.eng_option import eng_option
from gnuradio.filter import firdes
from grc_gnuradio import blks2 as grc_blks2
from grc_gnuradio import wxgui as grc_wxgui
from optparse import OptionParser
import wx

def setup_parser():
    """ Setup the parser for the frequency hopper. """
    parser = argparse.ArgumentParser(
            description="Transmit a signal in a frequency-hopping manner, using tx_freq tags."
    )
    parser.add_argument('-i', '--input-file', type=file, default=None,
            help="File with samples to transmit. If left out, will transmit a sinusoid.")
    parser.add_argument("-a", "--args", default="",
            help="UHD device address args.")
    parser.add_argument("--spec", default="",
            help="UHD subdev spec.")
    parser.add_argument("--antenna", default="",
            help="UHD antenna settings.")
    parser.add_argument("--gain", default=None, type=float,
            help="USRP gain (defaults to mid-point in dB).")
    parser.add_argument("-r", "--rate", type=float, default=1e6,
            help="Sampling rate")
    parser.add_argument("-N", "--samp-per-burst", type=int, default=10000,
            help="Samples per burst")
    parser.add_argument("-t", "--hop-time", type=float, default=1000,
            help="Time between hops in milliseconds. This must be larger than or equal to the burst duration as set by --samp-per-burst")
    parser.add_argument("-f", "--freq", type=float, default=2.45e9,
            help="Base frequency. This is the lowest frequency at which the USRP will Tx.")
    parser.add_argument("-d", "--freq-delta", type=float, default=1e6,
            help="Channel spacing.")
    parser.add_argument("-c", "--num-channels", type=int, default=5,
            help="Number of channels.")
    parser.add_argument("-B", "--num-bursts", type=int, default=30,
            help="Number of bursts to transmit before terminating.")
    parser.add_argument("-p", "--post-tuning", action='count',
            help="Tune after transmitting. Default is to tune immediately before transmitting.")
    parser.add_argument("-v", "--verbose", action='count',
            help="Print more information.")
    return parser

class FrequencyHopperSrc(gr.hier_block2):
    """ Provides tags for frequency hopping """
    def __init__(
            self,
            n_bursts, n_channels,
            freq_delta, base_freq,
            burst_length, base_time, hop_time,
            post_tuning=True,
            tx_gain=0,
            verbose=False
        ):
        gr.hier_block2.__init__(self,
            "FrequencyHopperSrc",
            gr.io_signature(1, 1, gr.sizeof_gr_complex),
            gr.io_signature(1, 1, gr.sizeof_gr_complex),
        )
        n_samples_total = n_bursts * burst_length
        self.hop_sequence = numpy.arange(base_freq, base_freq + n_channels * freq_delta, freq_delta)
      # self.hop_sequence = 2440000000, 2450000000, 2435000000, 2430000000, 2445000000, 2420000000, 2425000000  #Specify the hopping pattern here, repeat from begining
        numpy.random.shuffle(self.hop_sequence)  #this randomly shuffels frequencies in the specified range
        self.hop_sequence = [self.hop_sequence[x % n_channels] for x in xrange(n_bursts)]
      # self.hop_sequence = [self.hop_sequence[x % 7]for x in xrange(n_bursts)]
        if verbose:
            print "Hop Frequencies  | Hop Pattern"
            print "=================|================================"
            for f in self.hop_sequence:
                print "{:6.3f} MHz      |  ".format(f/1e6),
                if n_channels < 50:
                    print " " * int((f - base_freq) / freq_delta) + "#"
                else:
                    print "\n"
            print "=================|================================"
        # There's no real point in setting the gain via tag for this application,
        # but this is an example to show you how to do it.
        gain_tag = gr.tag_t()
        gain_tag.offset = 0
        gain_tag.key = pmt.string_to_symbol('tx_command')
        gain_tag.value = pmt.cons(
                pmt.intern("gain"),
                # These are both valid:
                #pmt.from_double(tx_gain)
                pmt.cons(pmt.to_pmt(0), pmt.to_pmt(tx_gain))
        )
        tag_list = [gain_tag,]
        for i in xrange(n_bursts):
            tune_tag = gr.tag_t()
            tune_tag.offset = i * burst_length
            if i > 0 and post_tuning:
                tune_tag.offset -= 1 # Move it to last sample of previous burst
            tune_tag.key = pmt.string_to_symbol('tx_freq')
            tune_tag.value = pmt.to_pmt(self.hop_sequence[i])
            tag_list.append(tune_tag)
            length_tag = gr.tag_t()
            length_tag.offset = i * burst_length
            length_tag.key = pmt.string_to_symbol('packet_len')
            length_tag.value = pmt.from_long(burst_length)
            tag_list.append(length_tag)
            time_tag = gr.tag_t()
            time_tag.offset = i * burst_length
            time_tag.key = pmt.string_to_symbol('tx_time')
            time_tag.value = pmt.make_tuple(
                    pmt.from_uint64(int(base_time + i * hop_time)),
                    pmt.from_double((base_time + i * hop_time) % 1),
            )
            tag_list.append(time_tag)
        tag_source = blocks.vector_source_c((1.0,) * n_samples_total, repeat=False, tags=tag_list)
        mult = blocks.multiply_cc()
        self.connect(self, mult, self)
        self.connect(tag_source, (mult, 1))


class FlowGraph(gr.top_block):
    """ Flow graph that does the frequency hopping. """
    def __init__(self, options):
        gr.top_block.__init__(self)

        # Setup USRP
        self.u = uhd.usrp_sink(options.args, uhd.stream_args('fc32'), "packet_len")
        if(options.spec):
            self.u.set_subdev_spec(options.spec, 0)
        if(options.antenna):
            self.u.set_antenna(options.antenna, 0)
        self.u.set_samp_rate(options.rate)
        # Gain is set in the hopper block
        if options.gain is None:
            g = self.u.get_gain_range()
            options.gain = float(g.start()+g.stop())/2.0
        print "-- Setting gain to {} dB".format(options.gain)
        r = self.u.set_center_freq(options.freq)
        if not r:
            print '[ERROR] Failed to set base frequency.'
            raise SystemExit, 1
        hopper_block = FrequencyHopperSrc(
                options.num_bursts, options.num_channels,
                options.freq_delta, options.freq,
                options.samp_per_burst, 1.0, options.hop_time / 1000.,
                options.post_tuning,
                options.gain,
                options.verbose,
        )

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 32000

        ##################################################
        # Blocks
        ##################################################
#        self.root_raised_cosine_filter_0 = filter.fir_filter_ccf(1, firdes.root_raised_cosine(1, samp_rate, 1, 0.35, 11*samp_rate))

        self.digital_dxpsk_mod_0 = digital.dqpsk_mod(
        	samples_per_symbol=4,
        	excess_bw=0.35,
        	mod_code="gray",
        	verbose=False,
        	log=False)

        self.blocks_vector_source_x_0 = blocks.vector_source_b((1, 0), True, 1, [])
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_vcc((0.500, ))
        self.blks2_packet_encoder_0 = grc_blks2.packet_mod_b(grc_blks2.packet_encoder(
        		samples_per_symbol=1,
        		bits_per_symbol=1,
        		preamble="",
        		access_code="11111111",
        		pad_for_usrp=True,
        	),
        	payload_length=0,
        )
    
        self.connect(self.blocks_vector_source_x_0, self.blks2_packet_encoder_0, self.digital_dxpsk_mod_0, self.blocks_multiply_const_vxx_0, hopper_block, self.u)

def print_hopper_stats(args):
    """ Nothing to do with Grace Hopper """
    print """
Parameter          | Value
===================+=========================
Hop Interval       | {hop_time} ms
Burst duration     | {hop_duration} ms
Lowest Frequency   | {lowest_freq:6.3f} MHz
Highest Frequency  | {highest_freq:6.3f} MHz
Frequency spacing  | {freq_delta:6.4f} MHz
Number of channels | {num_channels}
Sampling rate      | {rate} Msps
Transmit Gain      | {gain} dB
===================+=========================
    """.format(
            hop_time=args.hop_time,
            hop_duration=1000.0/args.rate*args.samp_per_burst,
            gain=args.gain,
            lowest_freq=args.freq/1e6,
            highest_freq=(args.freq + (args.num_channels-1) * args.freq_delta)/1e6,
            freq_delta=args.freq_delta/1e6,
            num_channels=args.num_channels,
            rate=args.rate/1e6,
        )

def main():
    """ Go, go, go! """
    args = setup_parser().parse_args()
    if (1.0 * args.samp_per_burst / args.rate) > args.hop_time * 1e-3:
        print "Burst duration must be smaller than hop time."
        raise SystemExit, 1
    if args.verbose:
        print_hopper_stats(args)
    top_block = FlowGraph(args)
    print "Starting to hop, skip and jump... press Ctrl+C to exit."
    top_block.u.set_time_now(uhd.time_spec(0.0))
    top_block.run()


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        pass

