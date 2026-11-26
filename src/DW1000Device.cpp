/*
 * Copyright (c) 2015 by Thomas Trojer <thomas@trojer.net> and Leopold Sayous <leosayous@gmail.com>
 * Decawave DW1000 library for arduino.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * @file DW1000Device.cpp
 * Arduino global library (source file) working with the DW1000 library
 * for the Decawave DW1000 UWB transceiver IC.
 *
 * Modified by Jaime Pérez (2025-2026) for the UWB-Train-Integrity project:
 * see the repository history for the changes.
 */

#include "DW1000Device.h"
#include "DW1000.h"


/*Constructor and destructor*/
DW1000Device::DW1000Device() {
	randomShortAddress();
}

DW1000Device::DW1000Device(byte deviceAddress[], bool shortOne) {
	if(!shortOne) {
		//The received address is long. Save it using setAddress, instead of setShortAddress
		setAddress(deviceAddress);
		randomShortAddress();
	}
	else {
		// Address received is short, now I use setSHORTAddress
		setShortAddress(deviceAddress);
	}
}

DW1000Device::DW1000Device(byte deviceAddress[], byte shortAddress[]) {
	
	// This constructor receives both types: the long & short addresses.
	setAddress(deviceAddress); 		// To save the long one
	setShortAddress(shortAddress); 	// Saves the short.
}

DW1000Device::~DW1000Device() { }



/*SETTERS*/

void DW1000Device::setReplyTime(uint16_t replyDelayTimeUs) { _replyDelayTimeUS = replyDelayTimeUs; }

void DW1000Device::setAddress(char deviceAddress[]) {
	DW1000.convertToByte(deviceAddress, _ownAddress); 
}

void DW1000Device::setAddress(byte* deviceAddress) {
	memcpy(_ownAddress, deviceAddress, 8);
}

void DW1000Device::setShortAddress(byte deviceAddress[]) {
	memcpy(_shortAddress, deviceAddress, 2);
}


void DW1000Device::setRange(float range) 	 { _range   = round(range*100);   }

void DW1000Device::setRXPower(float RXPower) { _RXPower = round(RXPower*100); }

void DW1000Device::setFPPower(float FPPower) { _FPPower = round(FPPower*100); }

void DW1000Device::setQuality(float quality) { _quality = round(quality*100); }


/*GETTERS*/

byte* DW1000Device::getByteAddress() {	return _ownAddress; }

byte* DW1000Device::getByteShortAddress() {	return _shortAddress; }

uint16_t DW1000Device::getShortAddress() {	return _shortAddress[1]*256+_shortAddress[0]; }

uint8_t DW1000Device::getShortAddressHeader(){	return _shortAddress[0]; }

float DW1000Device::getRange() { return float(_range)/100.0f; }

float DW1000Device::getRXPower() { return float(_RXPower)/100.0f; }

float DW1000Device::getFPPower() { return float(_FPPower)/100.0f; }

float DW1000Device::getQuality() { return float(_quality)/100.0f; }



/*Other Methods*/

void DW1000Device::randomShortAddress() {
	_shortAddress[0] = random(0, 256);
	_shortAddress[1] = random(0, 256);
}

bool DW1000Device::isAddressEqual(DW1000Device* device) {
	return memcmp(this->getByteAddress(), device->getByteAddress(), 8) == 0;
}

bool DW1000Device::isShortAddressEqual(DW1000Device* device) {
	return memcmp(this->getByteShortAddress(), device->getByteShortAddress(), 2) == 0;
}



void DW1000Device::noteActivity() {
	//Saves the last momento in which a device was seen alive. Used to determine if it is dead or not yet.
	_activity = millis();
}

bool DW1000Device::isInactive() {
	//If the activity has been too long ago (more than Inactivity time), then returns true, and the inactiveDevice callback will be launched.
	if(millis()-_activity > INACTIVITY_TIME) {
		_activity = millis();
		return true;
	}
	return false;
}