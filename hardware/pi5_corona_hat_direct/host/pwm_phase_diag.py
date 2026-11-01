import subprocess, time, os
P="/sys/class/pwm/pwmchip0"
def sh(*a): return subprocess.run(a,capture_output=True,text=True).stdout.strip()
def pw(p,v): open(p,"w").write(str(v))
def lv(): a,b=sh("pinctrl","lev","18,19").split(); return int(a),int(b)
assert sh("pinctrl","lev","24")=="0" and sh("pinctrl","lev","25")=="0", "driver must be asleep / bridge off"
def stats(tag,n=300):
    s=[lv() for _ in range(n)]
    f1=sum(a for a,_ in s)/n; f2=sum(b for _,b in s)/n; both=sum(a and b for a,b in s)/n; diff=sum(a!=b for a,b in s)/n
    print(f"{tag:42s} IN1 {f1*100:4.0f}%  IN2 {f2*100:4.0f}%  both {both*100:4.0f}%  differ {diff*100:4.0f}%")
for freq in (32000, 1000):
    T=round(1e9/freq)
    for ch in (2,3):
        if not os.path.isdir(f"{P}/pwm{ch}"): pw(f"{P}/export",ch); time.sleep(0.3)
        pw(f"{P}/pwm{ch}/enable",0); pw(f"{P}/pwm{ch}/polarity","normal"); pw(f"{P}/pwm{ch}/duty_cycle",0); pw(f"{P}/pwm{ch}/period",T)
    for pol3 in ("normal","inversed"):
        for trial in range(3):
            for ch in (2,3): pw(f"{P}/pwm{ch}/enable",0)
            pw(f"{P}/pwm3/polarity","normal")
            pw(f"{P}/pwm2/duty_cycle",T//2); pw(f"{P}/pwm3/duty_cycle",T//2)
            pw(f"{P}/pwm3/polarity",pol3)
            pw(f"{P}/pwm2/enable",1); pw(f"{P}/pwm3/enable",1); time.sleep(0.01)
            stats(f"{freq/1000:g} kHz ch3 {pol3:8s} trial {trial}")
    # ch2 alone
    for ch in (2,3): pw(f"{P}/pwm{ch}/enable",0)
    pw(f"{P}/pwm3/polarity","normal"); pw(f"{P}/pwm2/enable",1); time.sleep(0.01); stats(f"{freq/1000:g} kHz ch2 only 50%")
    pw(f"{P}/pwm2/enable",0)
for ch in (2,3):
    pw(f"{P}/pwm{ch}/enable",0); pw(f"{P}/pwm{ch}/polarity","normal")
print("final", lv(), "24/25", sh("pinctrl","lev","24"), sh("pinctrl","lev","25"))
