from plugins.p1_caller_rewards import CallerRewards
from plugins.p2_redemption import Redemption
from plugins.p3_my_rewards import MyRewards
from plugins.p4_governance import Governance
from plugins.p5_prizes import Prizes
from plugins.p6_rule_changes import RuleChanges
from plugins.p7_longtail_bugs import LongTailBugs

# Order matters a little: #1 discovers contracts that #7 then reviews.
ALL = [CallerRewards, Redemption, MyRewards, Governance, Prizes, RuleChanges, LongTailBugs]
BY_KEY = {p.key: p for p in ALL}
