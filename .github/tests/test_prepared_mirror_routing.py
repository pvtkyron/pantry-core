"""Execute mirror routing against published-source and distinct prepared-producer fixtures."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
SOURCE="a"*40
RECIPE="b"*40
def step(path,name):
    doc=yaml.safe_load((ROOT/"workflows"/path).read_text(encoding="utf-8"))
    return next(s["run"] for job in doc["jobs"].values() for s in job.get("steps",[]) if s.get("name")==name)

class PreparedMirrorRoutingTests(unittest.TestCase):
    def execute(self,program,env,prefix=""):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/"output"
            values=os.environ|env|{"GITHUB_OUTPUT":str(output),"TEST_FLAG":str(Path(temp)/"dispatched")}
            result=subprocess.run(["bash","-c",prefix+"\n"+program],env=values,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return result.stdout,output.read_text() if output.exists() else ""
    def test_new_prepared_delivery_publishes_even_when_source_and_checkpoint_exist(self):
        program=step("pantry-mirror.yml","Compare current published Pantry source")
        program=program.replace("${{ steps.source.outputs.pantry_sha }}",SOURCE)
        for producer,expected in (("101","true"),("","false")):
            with self.subTest(producer=producer):
                _,out=self.execute(program,{"GH_TOKEN":"fixture-token","DELIVERY_RUN_ID":producer,"TEST_SOURCE":SOURCE},
                    "gh(){ printf '%s\\n' \"$TEST_SOURCE\"; }")
                self.assertIn("needs_publish="+expected,out)
    def test_lane_recheck_does_not_discard_a_new_delivery_of_same_source(self):
        program=step("pantry-mirror.yml","Recheck source after acquiring the publication lane")
        for producer,expected in (("101","true"),("","false")):
            with self.subTest(producer=producer):
                _,out=self.execute(program,{"GH_TOKEN":"fixture-token","SOURCE_SHA":SOURCE,"DELIVERY_RUN_ID":producer,"TEST_SOURCE":SOURCE},
                    "gh(){ printf '%s\\n' \"$TEST_SOURCE\"; }")
                self.assertIn("needs_publish="+expected,out)
    def invoke_box(self,prior):
        program=step("box.yml","Publish exact Pantry revision through canonical mirror")
        current={"databaseId":202,"displayTitle":"Pantry mirror "+SOURCE+" delivery 101/2",
                 "createdAt":"9999-01-01T00:00:00Z","status":"completed","conclusion":"success","headSha":RECIPE}
        prefix="""gh(){
  if [[ "$1" == run && "$2" == list ]]; then
    if [[ -f "$TEST_FLAG" ]]; then printf '%s\\n' "$TEST_CURRENT"; else printf '%s\\n' "$TEST_PRIOR"; fi
  elif [[ "$1" == api ]]; then printf '%s\\n' "$TEST_SOURCE"
  elif [[ "$1" == workflow && "$2" == run ]]; then : > "$TEST_FLAG"; echo FIXTURE_DISPATCHED
  else return 99; fi
}"""
        return self.execute(
            program,{"PANTRY_SHA":SOURCE,"GITHUB_REPOSITORY":"pvtkyron/pantry-core","GITHUB_RUN_ID":"101",
            "GITHUB_RUN_ATTEMPT":"2","GITHUB_SHA":RECIPE,"TEST_SOURCE":SOURCE,"TEST_PRIOR":json.dumps(prior),
            "TEST_CURRENT":json.dumps([current])},prefix)[0]
    def fixture(self,title,status="completed",attempt=1):
        return {"databaseId":100+attempt,"displayTitle":title,"createdAt":"2026-01-01T00:00:00Z",
            "status":status,"conclusion":"success" if status=="completed" else "","headSha":RECIPE}
    def test_prior_source_success_and_other_producer_cannot_suppress_new_delivery(self):
        prior=[self.fixture("Pantry mirror "+SOURCE),
               self.fixture("Pantry mirror "+SOURCE+" delivery 100/2","in_progress")]
        out=self.invoke_box(prior)
        self.assertIn("FIXTURE_DISPATCHED",out);self.assertNotIn("already_published=true",out)
    def test_different_attempt_cannot_reuse_the_prior_signed_payload(self):
        out=self.invoke_box([self.fixture("Pantry mirror "+SOURCE+" delivery 101/1")])
        self.assertIn("FIXTURE_DISPATCHED",out)
    def test_exact_successful_producer_can_be_reused(self):
        out=self.invoke_box([self.fixture("Pantry mirror "+SOURCE+" delivery 101/2")])
        self.assertIn("already_published=true",out);self.assertNotIn("FIXTURE_DISPATCHED",out)

if __name__=="__main__":unittest.main(verbosity=2)
