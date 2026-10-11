require_relative 'kicad_sexp'
b=File.expand_path('..',__dir__)+'/'
after=Sch.new(ARGV.fetch(0)).root
connections=->(root){root.child('nets').children('net').map{|n|[n.child('name').v,n.children('node').map{|p|[p.child('ref').v,p.child('pin').v]}.sort]}.sort}
components=after.child('components').children('comp').map do |c|
 props=c.children('property').to_h{|p|[p.child('name').v,p.child('value')&.v||'']}
 c.child('fields')&.children('field')&.each{|f|props[f.child('name').v]=f.v(2)||''}
 {ref:c.child('ref').v,value:c.child('value').v,footprint:c.child('footprint').v,path:c.child('sheetpath').child('tstamps').v+c.child('tstamps').v,properties:props}
end
nets=after.child('nets').children('net').map{|n|{code:n.child('code').v.to_i,name:n.child('name').v,nodes:n.children('node').map{|p|[p.child('ref').v,p.child('pin').v]}}}
File.write(b+'layout/schematic-connectivity.json',JSON.pretty_generate({components:components,nets:nets})+"\n")
puts 'Updated connectivity manifest'
