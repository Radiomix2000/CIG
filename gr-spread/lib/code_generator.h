/* -*- c++ -*- */
/* 
 * Copyright 2014 Paul David <pudavid@vt.edu>
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef INCLUDED_SPREAD_CODE_GENERATOR_H
#define INCLUDED_SPREAD_CODE_GENERATOR_H

#include <vector> 

#include "common.h"

class LFSR  
{
 public:
  const int nreg; 

  LFSR(polynomial gen, polynomial init); 

  void update(); 
  void reset(); 

  bit getRegister(int pos) const;  
  polynomial * getRegisters() const; 
  int getFrequency() const; 

 private: 
  polynomial _init; 
  polynomial generator; 
  polynomial state; 

}; 

#endif /* INCLUDED_SPREAD_CODE_GENERATOR_H */

