import unittest
from agents.dendrite_route_evolution import search_routes
HEAD='a'*40
class RouteEvolutionTests(unittest.TestCase):
    def test_six_topics_have_search_traces(self):
        r=search_routes(head=HEAD)
        self.assertEqual(len(r['topics']),6)
        self.assertTrue(all(len(x['search_trace'])==9 for x in r['topics']))
    def test_no_quarantine_leaks(self):
        r=search_routes(head=HEAD)
        self.assertTrue(all(x['quarantine_invariant']=='PASS' for x in r['topics']))
    def test_candidate_never_auto_admitted(self):
        r=search_routes(head=HEAD)
        self.assertEqual(r['promotion'],'DENIED')
        self.assertEqual(r['authority_effect'],'NONE')
        self.assertTrue(all(x['candidate'] is None or x['candidate']['status']=='NOT_ADMITTED' for x in r['topics']))
    def test_deterministic(self):
        self.assertEqual(search_routes(head=HEAD),search_routes(head=HEAD))
    def test_bad_baseline(self):
        with self.assertRaisesRegex(ValueError,'ROUTE_BASELINE_INVALID'):
            search_routes(head=HEAD,baseline_ttl=9)
    def test_actual_routing_optimization(self):
        r=search_routes(head=HEAD)
        self.assertTrue(any(x['candidate'] is not None for x in r['topics']))
        self.assertTrue(all(x['candidate'] is None or x['candidate']['delivery_delta']<0 for x in r['topics']))
    def test_unmatched_baseline_cannot_claim_improvement(self):
        r=search_routes(head=HEAD,baseline_ttl=0)
        self.assertTrue(all(x['candidate'] is None for x in r['topics']))
    def test_no_external_metric_claim(self):
        self.assertEqual(search_routes(head=HEAD)['external_benchmark'],'NOT_PERFORMED')
if __name__=='__main__':unittest.main()
