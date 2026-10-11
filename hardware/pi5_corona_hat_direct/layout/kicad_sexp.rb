require 'json'
class Node
 attr_accessor :kids
 def initialize(k); @kids=k; end
 def key; @kids[0]; end
 def child(k); @kids.find{|x| x.is_a?(Node)&&x.key==k}; end
 def children(k); @kids.select{|x|x.is_a?(Node)&&x.key==k}; end
 def v(i=1); a=@kids[i]; a && a.start_with?('"') ? JSON.parse(a) : a; end
 def set(i,v); @kids[i]=v.is_a?(String) ? JSON.generate(v) : v.to_s; end
 def dump(indent=0)
  return '('+@kids.join(' ')+')' if @kids.none?{|x|x.is_a?(Node)}
  atoms=@kids.take_while{|x|!x.is_a?(Node)}
  '('+atoms.join(' ')+"\n"+@kids[atoms.size..].map{|x| "\t"*(indent+1)+(x.is_a?(Node) ? x.dump(indent+1) : x)}.join("\n")+"\n"+"\t"*indent+')'
 end
end
class Sch
 attr_accessor :root,:path
 def initialize(p)
  @path=p; ts=File.read(p).scan(/"(?:\\.|[^"\\])*"|[()]|[^\s()]+/); stack=[]; ts.each{|t| if t=='('; stack << []; elsif t==')'; n=Node.new(stack.pop); stack.empty? ? @root=n : stack.last<<n; else; stack.last<<t; end}
 end
 def objects(k); @root.children(k); end
 def comps; objects('symbol'); end
 def ref(s); s.children('property').find{|p|p.v=='Reference'}&.v(2); end
 def pos(s); n=s.child('at'); [n.kids[1].to_f,n.kids[2].to_f]; end
 def pins(s)
  lib=@root.child('lib_symbols').children('symbol').find{|l|l.v==s.child('lib_id').v}; x,y=pos(s); angle=s.child('at').kids[3].to_f*Math::PI/180; unit=s.child('unit').v.to_i
  lib.children('symbol').select{|l|u=l.v.split('_')[-2].to_i;u==0||u==unit}.flat_map{|u|u.children('pin')}.map{|p|a=p.child('at');px=a.kids[1].to_f;py=a.kids[2].to_f;m=s.child('mirror');px=-px if m&&m.v=='y';py=-py if m&&m.v=='x'; [x+px*Math.cos(angle)+py*Math.sin(angle),y+px*Math.sin(angle)-py*Math.cos(angle)]}.map{|p|p.map{|v|v.round(5)}}
 end
 def save; File.write(@path,@root.dump+"\n");end
 def all; @root.kids.select{|x|x.is_a?(Node)};end
 def translate(n,dx,dy)
  n.kids.each{|k| next unless k.is_a?(Node); if %w[at xy start end].include?(k.key);k.kids[1]=fmt(k.kids[1].to_f+dx);k.kids[2]=fmt(k.kids[2].to_f+dy);else;translate(k,dx,dy);end}
 end
 def fmt(v); v.round(5).to_s;end
 def islands
  comps=comps(); parent={};find=->(k){parent[k]||=k;parent[k]==k ? k : parent[k]=find.call(parent[k])}; union=->(a,b){parent[find.call(a)]=find.call(b)}; key=->(p){p.map{|v|v.round(4)}.join(',')}
  entries={}; comps.each{|s|ps=pins(s).map{|p|key.call(p)};ps.each{|p|find.call(p)};ps.each_cons(2){|a,b|union.call(a,b)};entries[s]=ps}
  objects('wire').each{|w|ps=w.child('pts').children('xy').map{|a|key.call([a.kids[1].to_f,a.kids[2].to_f])}; union.call(*ps);entries[w]=ps}
  %w[label global_label hierarchical_label junction no_connect].each{|k|objects(k).each{|n|entries[n]=[key.call(pos(n))];find.call(entries[n][0])}}
  # A pin, label or junction landing mid-wire is part of that same drawn island.
  entries.keys.select{|n|n.key=='wire'}.each{|w|coords=w.child('pts').children('xy').map{|n|[n.kids[1].to_f,n.kids[2].to_f]};a,b=coords;parent.keys.each{|k|x,y=k.split(',').map(&:to_f);if (a[0]==b[0] && (x-a[0]).abs<0.0001 && y>= [a[1],b[1]].min && y<= [a[1],b[1]].max)||(a[1]==b[1]&&(y-a[1]).abs<0.0001&&x>= [a[0],b[0]].min&&x<=[a[0],b[0]].max);union.call(entries[w][0],k);end}}
  entries.group_by{|n,ps|find.call(ps[0])}.values.map{|en|en.map(&:first)}
 end
 def move_island(ref,x,y)
  island=islands.find{|g|g.any?{|s|s.key=='symbol'&&self.ref(s)==ref}};s=island.find{|o|o.key=='symbol'&&self.ref(o)==ref};ox,oy=pos(s);island.each{|n|translate(n,x-ox,y-oy)}
 end
end
