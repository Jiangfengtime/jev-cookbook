"""数独服务的契约与并发回归；MockTransport 仅在测试中注入，不是应用运行模式。"""
import copy
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve_sudoku import Game, InputError, JevGateway, SudokuApp
import sudoku_game as S
from jev_sudoku import run_episode


class LiveSudokuTests(unittest.TestCase):
    def gateway(self, handler):
        config = {"TYPESAFE_API_KEY": "fixture-key-do-not-expose", "TYPESAFE_DEFAULT_MODEL": "configured-model",
                  "TYPESAFE_BASE_URL": "https://configured.example/compatible-mode"}
        with patch('serve_sudoku.load_project_env'), patch.dict('os.environ', config):
            return JevGateway(transport=httpx2.MockTransport(handler))

    def payload(self, request, digit='4'):
        body = json.loads(request.content)
        answers = {k: {"type": "noul", "noul": .5} for k in body['questions'] if k != 'digit'}
        answers['digit'] = {"type": "choice", "choice": digit, "confidence": .8,
                            "probabilities": {str(d): float(str(d) == digit) for d in S.DIGITS}}
        return {"model": "configured-model", "answers": answers,
                "usage": {"input_tokens": 12}, "request_id": "actual-extra-field"}

    def test_actual_sdk_wire_capture_preserves_extra_fields_without_secrets_or_gold(self):
        sent = []
        def handler(request):
            sent.append(request)
            self.assertEqual(str(request.url), 'https://configured.example/compatible-mode/v1/systemone')
            self.assertEqual(request.headers['Authorization'], 'Bearer fixture-key-do-not-expose')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'configured-model')
            self.assertEqual(len(body['questions']), 10)
            self.assertTrue(all(q['type'] == 'noul' for k,q in body['questions'].items() if k != 'digit'))
            self.assertNotIn('solution', body['state'])
            self.assertNotIn('gold', body['state'])
            self.assertNotIn('seed', body['state'])
            return httpx2.Response(200, json=self.payload(request), headers={'x-server-field':'retained'})
        gateway = self.gateway(handler);app = SudokuApp(gateway);initial = app.create({'case_id':'warmup'})
        self.assertFalse(initial['running']);self.assertEqual(sent, [])
        result = app.advance(initial['id'], {'expected_steps':0,'single':True})
        self.assertEqual(result['steps'],1);self.assertEqual(result['score'],1)
        trace = result['history'][0]
        self.assertEqual(json.loads(trace['request']['body_text']), json.loads(sent[0].content))
        self.assertEqual(trace['response']['body']['request_id'], 'actual-extra-field')
        self.assertIn(['x-server-field','retained'],trace['response']['headers'])
        self.assertNotIn(gateway.key,json.dumps(result))
        self.assertIn('[REDACTED]',json.dumps(trace))
        self.assertNotIn('solution',result)
        with self.assertRaises(InputError):app.advance(initial['id'],{'expected_steps':0,'single':True})
        self.assertEqual(len(sent),1)

    def test_pause_invalidates_inflight_move_and_retains_response(self):
        entered,release = threading.Event(),threading.Event()
        def handler(request):
            entered.set();self.assertTrue(release.wait(4))
            return httpx2.Response(200,json=self.payload(request))
        app=SudokuApp(self.gateway(handler));initial=app.create({'case_id':'warmup'});gid=initial['id']
        app.control(gid,{'action':'run'});results=[]
        worker=threading.Thread(target=lambda:results.append(app.advance(gid,{'expected_steps':0})))
        worker.start();self.assertTrue(entered.wait(3))
        try:
            paused=app.control(gid,{'action':'pause'})
            self.assertTrue(paused['busy']);self.assertFalse(paused['running'])
            with self.assertRaises(InputError):app.advance(gid,{'expected_steps':0})
        finally:release.set();worker.join(4)
        self.assertFalse(worker.is_alive());result=results[0]
        self.assertEqual(result['grid'],initial['grid']);self.assertEqual(result['steps'],0)
        self.assertFalse(result['history'][0]['applied']);self.assertIsNotNone(result['history'][0]['response'])
        app.control(gid,{'action':'run'})
        resumed=app.advance(gid,{'expected_steps':0})
        self.assertEqual(resumed['score'],1)

    def test_switching_case_pauses_old_game_and_isolates_history(self):
        app=SudokuApp(self.gateway(lambda r:httpx2.Response(200,json=self.payload(r))))
        old=app.create({'case_id':'warmup'});app.control(old['id'],{'action':'run'})
        new=app.create({'case_id':'standard','previous_game':old['id']})
        self.assertNotEqual(new['grid'],old['grid']);self.assertNotEqual(new['id'],old['id'])
        self.assertFalse(new['running']);self.assertFalse(app.game(old['id']).running)
        self.assertEqual(new['history'],[]);self.assertEqual(new['steps'],0)
        with self.assertRaises(InputError):app.advance(old['id'],{'expected_steps':0})

    def test_switch_during_request_cannot_write_into_new_or_old_board(self):
        entered,release=threading.Event(),threading.Event()
        def handler(request):
            entered.set();release.wait(4);return httpx2.Response(200,json=self.payload(request))
        app=SudokuApp(self.gateway(handler));old=app.create({'case_id':'warmup'});results=[]
        worker=threading.Thread(target=lambda:results.append(app.advance(old['id'],{'single':True,'expected_steps':0})))
        worker.start();self.assertTrue(entered.wait(3))
        try:new=app.create({'case_id':'custom','seed':2,'holes':3,'previous_game':old['id']})
        finally:release.set();worker.join(4)
        self.assertEqual(new['score'],0);self.assertEqual(new['history'],[])
        self.assertEqual(results[0]['steps'],0);self.assertFalse(results[0]['history'][0]['applied'])

    def test_http_error_is_visible_and_pauses_without_fallback(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx2.Response(401,json={'error':'denied','echo':'fixture-key-do-not-expose'})
        app=SudokuApp(self.gateway(handler));initial=app.create({});gid=initial['id']
        app.control(gid,{'action':'run'});result=app.advance(gid,{'expected_steps':0})
        self.assertEqual(len(calls),1);self.assertEqual(result['grid'],initial['grid'])
        self.assertEqual(result['steps'],0);self.assertFalse(result['running'])
        self.assertEqual(result['history'][0]['response']['status'],401)
        self.assertNotIn('fixture-key-do-not-expose',json.dumps(result))
        with self.assertRaises(InputError):app.advance(gid,{'expected_steps':0})

    def test_wrong_digit_counts_without_board_write_and_is_published_next_time(self):
        bodies=[]
        def handler(request):
            bodies.append(json.loads(request.content));return httpx2.Response(200,json=self.payload(request,'1'))
        app=SudokuApp(self.gateway(handler));initial=app.create({});gid=initial['id']
        result=app.advance(gid,{'single':True,'expected_steps':0})
        self.assertEqual(result['mistakes'],1);self.assertEqual(result['grid'],initial['grid'])
        app.advance(gid,{'single':True,'expected_steps':1})
        result=app.advance(gid,{'single':True,'expected_steps':2})
        self.assertIn('已经尝试且证错',bodies[1]['state'])
        self.assertEqual(result['outcome'],'three_mistakes');self.assertFalse(result['running'])

    def test_missing_key_never_calls_transport_and_custom_input_is_checked(self):
        gateway=self.gateway(lambda _:self.fail('缺 Key 不得联网'));gateway.key=''
        app=SudokuApp(gateway);game=app.create({'case_id':'custom','seed':4,'holes':1})
        with self.assertRaises(InputError):app.advance(game['id'],{'single':True,'expected_steps':0})
        for data in [{'case_id':'invalid'}, {'case_id':'custom','seed':True,'holes':2}, {'case_id':'custom','seed':1,'holes':56}]:
            with self.assertRaises(InputError):app.create(data)

    def test_cli_gold_type_does_not_mark_correct_digits_wrong(self):
        def judge(request):
            return {'digit':str(request['candidates'][0])}
        result=run_episode(seed=1,holes=1,judge=judge)
        self.assertEqual(result['outcome'],'win');self.assertTrue(result['steps_detail'][0]['correct'])


if __name__=='__main__':unittest.main()
