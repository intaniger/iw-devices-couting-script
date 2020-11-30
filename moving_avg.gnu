set xdata time
set format x '%d/%m/%y %H:%M:%S'
set title "# of devices read in WiFi beacon. (interval=10secs, threshold=60 secs)" 
n = 30

# initialize the variables
do for [i=1:n] {
    eval(sprintf("back%d=0", i))
}

# build shift function (back_n = back_n-1, ..., back1=x)
shift = "("
do for [i=n:2:-1] {
    shift = sprintf("%sback%d = back%d, ", shift, i, i-1)
} 
shift = shift."back1 = x)"
# uncomment the next line for a check
# print shift

# build sum function (back1 + ... + backn)
sum = "(back1"
do for [i=2:n] {
    sum = sprintf("%s+back%d", sum, i)
}
sum = sum.")"
# uncomment the next line for a check
# print sum

# define the functions like in the gnuplot demo
# use macro expansion for turning the strings into real functions
samples(x) = $0 > (n-1) ? n : ($0+1)
avg_n(x) = (shift_n(x), @sum/samples($0))
shift_n(x) = @shift

datafile = "data.dat"
## Last datafile plotted: "silver.dat"
plot datafile using ($1 + (7 * 3600)):2 title 'raw data' lw 1 lt rgb "#C0C0C0",\
  '' using ($1 + (7 * 3600) - 150):(avg_n($2)) title "running mean over previous 30 points (left-shifting by 150 secs)" lw 3 pt 7 ps 0.5 w lines