# Read the native KiCad-exported connectivity manifest. Run after refreshing it.
require 'json'
root=File.expand_path('../..',__dir__)
m=JSON.parse(File.read(root+'/layout/schematic-connectivity.json'))
net={};m['nets'].each{|n|n['nodes'].each{|p|net[p.join('.')]=n['name']}}
checks={
 'independent GPIO inputs and commands'=>[%w[J2.16 J2.18 J2.22 U2.3 U9.1]],
 'relay bulk command contacts'=>[%w[J2.22 K1.3],%w[K1.4 U9.1]],
 'relay sleep command contacts'=>[%w[J2.18 K1.6],%w[K1.5 U2.3]],
 'coil regulation'=>[%w[U10.1 U10.3 J2.1],%w[U10.5 J64.1],%w[S3.1 J62.1]],
 'series mechanical interlocks'=>[
   %w[J64.2 J65.1],
   %w[J65.2 J68.1],
   %w[J68.2 J69.1],
   %w[J69.2 K1.1 R92.1 D3.1]
 ],
 'detachable switch boards'=>[
   %w[S3.1 J62.1], %w[S3.2 J62.2],
   %w[S4.1 J63.1], %w[S4.2 J63.2],
   %w[S5.1 J66.1], %w[S5.2 J66.2],
   %w[S6.1 J67.1], %w[S6.2 J67.2]
 ],
 'detachable optical sensor'=>[
   %w[J51.1 U8.3 C80.2 C81.2],
   %w[J51.2 U8.5 C80.1 C81.1],
   %w[J51.3 U8.6],
   %w[J51.4 U8.1]
 ],
 'host qwiic connector'=>[
   %w[J50.1 J2.6],
   %w[J50.2 J2.1],
   %w[J50.3 J2.3],
   %w[J50.4 J2.5]
 ],
 'limited interlock feedback'=>[%w[R92.2 J2.16]],
 'coil and regulator grounds'=>[%w[K1.8 U10.2 J2.6]],
 'correct transformer primary'=>[%w[T1.1 C11.2],%w[T1.5 U2.10]],
 'correct transformer secondary and guards'=>[%w[T1.8 T1.7],%w[T1.9 T1.10 T1.6 R90.2 D5.2],%w[J61.1 R90.1 D5.1]],
 'return surge clamp and ADC protection'=>[%w[D5.1 R91.1],%w[R91.2 D4.3]]
}
checks.each do |name,groups|
 groups.each{|g|raise "Missing pin: #{g}" unless g.all?{|p|net[p]}}
 if name=='independent GPIO inputs and commands'
  raise name unless groups[0].map{|p|net[p]}.uniq.length==groups[0].length
 else
  groups.each{|g|raise "Failed #{name}: #{g.map{|p|[p,net[p]]}}" unless g.map{|p|net[p]}.uniq.length==1}
 end
end
raise 'Transformer unused CT must remain NC' unless net['T1.3'].start_with?('unconnected-')
puts "PASS: #{checks.length} audit connectivity checks"
