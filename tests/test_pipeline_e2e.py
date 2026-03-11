import asyncio, sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_supabase
from modules.transcription.service import transcribe_job
from modules.emotion_engine.service import analyze_job
from modules.prediction_engine.service import predict_job
from modules.rewrite_engine.service import generate_rewrites_for_drop_moments
from modules.timeline.service import build_timeline

TEST_SCRIPT = """
Welcome to this video about our new productivity software.
The product has many features and functions that can help users.
It includes task management, calendar integration, and reporting tools.
You can also export data in multiple formats including CSV and PDF.
The interface is user-friendly and easy to navigate.

But here's what nobody tells you about staying productive: most tools 
are built around tasks, not around how humans actually think. We designed 
this differently. We started by studying how people lose focus — the 
exact moments when a to-do list stops working and anxiety takes over.

I spent three years building this after burning out at my last job.
I know what it feels like when your system collapses under pressure.
This tool was built from that experience, for people who've been there.

What if the real problem isn't productivity — it's recovery? 
What if the tool that finally works for you is the one that helps 
you rest as intelligently as you work? That's what we're building.
Try it free for 30 days. No credit card required.
""".strip()

async def run_test():
    print("\n" + "═"*60)
    print("  NeuroVibe Studio — Pipeline E2E Test")
    print("═"*60)
    db = get_supabase()
    project_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    print("\n[1/6] Creating test job...")
    db.table("projects").insert({"id": project_id, "title": "E2E Test", "user_id": "00000000-0000-0000-0000-000000000001"}).execute()
    db.table("jobs").insert({"id": job_id, "project_id": project_id, "user_id": "00000000-0000-0000-0000-000000000001", "status": "pending", "content_type": "script", "raw_script": TEST_SCRIPT, "meta": {}}).execute()
    print(f"    ✓ Job created: {job_id}")

    print("\n[2/6] Transcribing...")
    segments = await transcribe_job(job_id, db)
    print(f"    ✓ {len(segments)} segments created")
    for i, s in enumerate(segments):
        print(f"    [{i+1}] {s.time_start:.1f}s–{s.time_end:.1f}s | {s.text[:70]}...")

    print(f"\n[3/6] Running emotion analysis (GPT-4o)...")
    print("    ⏳ 15–40 seconds...")
    scored = await analyze_job(job_id, db)
    print(f"    ✓ {len(scored)} segments scored")
    print(f"\n    {'#':<4} {'Score':>6} {'Curiosity':>10} {'Warmth':>8} {'Trust':>7} {'Boredom':>8} {'Drop?':>7}")
    print("    " + "─"*55)
    for i, seg in enumerate(scored):
        s = seg.scores
        drop = "⚠️ YES" if seg.is_drop_moment else "no"
        print(f"    [{i+1:<2}] {seg.segment_score:>6.1f}  {s.curiosity:>10.2f} {s.warmth:>8.2f} {s.trust:>7.2f} {s.boredom_risk:>8.2f} {drop:>7}")
        if seg.is_drop_moment:
            print(f"         └─ {seg.drop_reason}")

    print(f"\n[4/6] Generating predictions...")
    pred = await predict_job(job_id, db)
    print(f"    ✓ Engagement Score:       {pred.engagement_score:.1f}/100")
    print(f"    ✓ Watch Time Probability: {pred.watch_time_probability:.1%}")
    print(f"    ✓ Share Likelihood:       {pred.share_likelihood:.1%}")
    print(f"    ✓ Conversion Likelihood:  {pred.conversion_likelihood:.1%}")
    print(f"    ✓ Drop Moments:           {len(pred.drop_moments)}")

    print(f"\n[5/6] Generating rewrites for drop moments...")
    rewrites = await generate_rewrites_for_drop_moments(job_id, db)
    print(f"    ✓ {len(rewrites)} rewrites generated")
    for r in rewrites:
        print(f"\n    ORIGINAL:  {r.get('original_text','')[:80]}...")
        print(f"    IMPROVED:  {r.get('improved_text','')[:80]}...")
        print(f"    TECHNIQUE: {r.get('technique_used','N/A')}")

    print(f"\n[6/6] Building timeline...")
    timeline = await build_timeline(job_id, db)
    print(f"    ✓ {len(timeline.points)} points, overall score: {timeline.overall_score:.1f}")

    print("\n" + "═"*60)
    print("  ✅ PIPELINE COMPLETE")
    print(f"  Engagement Score: {pred.engagement_score:.1f}/100")
    print(f"  Drop Moments:     {len(pred.drop_moments)}")
    print(f"  Rewrites Made:    {len(rewrites)}")
    print("═"*60)

    db.table("jobs").delete().eq("id", job_id).execute()
    db.table("projects").delete().eq("id", project_id).execute()
    print("\n  Test data cleaned up.\n")

if __name__ == "__main__":
    asyncio.run(run_test())
