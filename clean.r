

# cycle over all folders and get json data

library(jsonlite)
library(stringr)
library(data.table)
library(ggplot2)
library(xtable)


getData <- function(dir="~/Dropbox/bankruptcy/writeups/WL-CM-FO/WL_FO_Nevada/webscraper/output"){

	setwd(dir)
	outdir = list.files(dir)
	dt = data.table()
	l = list()
	for (d in 1:length(outdir)) {
		dt1 = data.table()
		for (f in list.files(outdir[d])){
			fp = file.path(outdir[d],f)
			cat(sprintf("reading file %s",fp),"\n")
			dt1 = rbind(dt1,getJson(fp),fill=TRUE)
		}
		dt = rbind(dt,dt1,fill=TRUE)
	}
	# get rid of some garbage columns
	dt[,names(dt)[str_detect(names(dt),"^X")] := NULL]

	# get rid of cases with more than 4 defendants or plaintiffs
	defs = names(dt)[str_detect(names(dt),"^Defendant_")]
	defdrop = unlist(lapply(strsplit(defs,"\\_"),function(x) as.numeric(x[2]) > 4))
	dt[,defs[defdrop] := NULL]
	defs = names(dt)[str_detect(names(dt),"^Plaintiff_")]
	defdrop = unlist(lapply(strsplit(defs,"\\_"),function(x) as.numeric(x[2]) > 4))
	dt[,defs[defdrop] := NULL]

	# some formatting
	# ===============

	# format dates
	dt[,EntryDate := as.Date(EntryDate,format="%m/%d/%Y")]
	dt[,Date_Filed := as.Date(Date_Filed,format="%m/%d/%Y")]
  dt[,quarter_filed := zoo::as.Date(zoo:::as.yearqtr(Date_Filed))]
	dt[,Year_Filed:= year(Date_Filed)]
  dt[,before2010 := TRUE]
	dt[Year_Filed>=2010,before2010 := FALSE]
  dt[,before2010 := factor(before2010,labels=c("Before 2010", "After 2010"))]
	# strip of whitespace first
	dt[,Description := str_trim(Description)]
	dt[,Disposition := str_trim(Disposition)]


	# the dataset has a discontinuity at year 2008. need to stack together different variable names.

	# for year < 2008, there is always a complete "Description" field. afterwards "Disposition" is always complete. combine
	dt[,disposition := tolower(Disposition)]
	dt[Year_Filed < 2008, disposition := tolower(Description)]

	# get numeric values for $ amounts
	dt[,amount_awarded := as.numeric(gsub("\\$|\\,","",Amount_Awarded))]
	dt[,total_judgment := as.numeric(gsub("\\$|\\,","",Total_Judgment))]
	dt[,attorney_fees := as.numeric(gsub("\\$|\\,","",Attorney_Fees))]

	dt[,total_awarded := amount_awarded]
	dt[Year_Filed > 2007,total_awarded := total_judgment]
	dt[,awarded_defendant := total_awarded / numDefendants]
	dt[,awarded_plaintiff := total_awarded / numPlaintiffs]

	# subsetting 
	# ==========

	# only cases where the bank is the plaintiff
	dt[, bank_plaintiff := tolower(Plaintiff_1) == tolower(Bank_search) | tolower(Plaintiff_2) == tolower(Bank_search) | tolower(Plaintiff_3) == tolower(Bank_search)]

	# search for Default Judgment terms
	terms = c("DEFAULT JUDGMENT","DFLT JDGMT","DFLT JMNT","JUDGMENT PLUS INTEREST","DEFAULT JUDGMENT PLUS INTEREST","DEFAULT JUDG \\+ INT","DEFAULT JUDGMT \\+ INT","JUDGMENT PLUS LEGAL INTEREST","DEFAULT JMNT + INTEREST","DFLT JMNT\\+LEGAL","DFLT JDGMT\\+INTEREST")
	idx = c()
	for (te in terms){
		tmp = str_detect(dt[,disposition],ignore.case(te))
		tmp[is.na(tmp)] = 0
		# print(sum(tmp))
		idx = cbind(idx,tmp)
	}
	idx =apply(idx,1,max)
	return( list(all=dt,deficiency=dt[as.logical(idx*bank_plaintiff)]) )
}

plots <- function(y){
	l = list()
	l$filings_by_year <- ggplot(y$deficiency[,.N,by=Year_Filed],aes(x=Year_Filed,y=N)) + geom_line()
	l$filings_by_qtr <- ggplot(y$deficiency[,.N,by=quarter_filed],aes(x=quarter_filed,y=N)) + geom_line() + scale_y_continuous(name="Number of Deficiency Judgments")
	l$amounts_by_qtr <- ggplot(y$deficiency[,list(Total_Awarded=median(total_awarded,na.rm=TRUE)),by=quarter_filed],aes(x=quarter_filed,y=Total_Awarded)) + geom_line() + scale_y_continuous(name="Median Amount Awarded (current $)")
	l$amounts_by_qtr_def <- ggplot(y$deficiency[,list(Total_Awarded=median(awarded_defendant,na.rm=TRUE)),by=quarter_filed],aes(x=quarter_filed,y=Total_Awarded)) + geom_line() + scale_y_continuous(name="Median Amount Awarded per defendant (current $)")
	l$amounts_by_qtr_plaintiff <- ggplot(y$deficiency[,list(Total_Awarded=median(awarded_plaintiff,na.rm=TRUE)),by=quarter_filed],aes(x=quarter_filed,y=Total_Awarded)) + geom_line() + scale_y_continuous(name="Median Amount Awarded per plaintiff (current $)")
  ggsave(plot=l$filings_by_year,file="analysis/filings_year.pdf")
	ggsave(plot=l$filings_by_qtr,file="analysis/filings_qtr.pdf")
	ggsave(plot=l$amounts_by_qtr,file="analysis/amounts_qtr.pdf")
	ggsave(plot=l$amounts_by_qtr_def,file="analysis/amounts_qtr_def.pdf")
	ggsave(plot=l$amounts_by_qtr_plaintiff,file="analysis/amounts_by_qtr_plaintiff.pdf")
	return(l)
}


tabs <- function(y){
  l = list()
  l$nums = dcast(y$deficiency[,.N,by=list(before2010,Bank_search)][order(N)],Bank_search ~ before2010)
  l$amounts = dcast(y$deficiency[,list(Awarded=median(total_awarded,na.rm=T)),by=list(before2010,Bank_search)],Bank_search ~ before2010)
  print(xtable(l$nums),file="analysis/num_filings.tex",include.rownames=FALSE,floating=FALSE,booktabs=TRUE)
  print(xtable(l$amounts),file="analysis/amount_filings.tex",include.rownames=FALSE,floating=FALSE,booktabs=TRUE)
  return(l)
}

getJson <- function(file){
	x = fromJSON(file)
	dt = data.table()

	for (ca in x$cases) {
		names(ca) = gsub("\\.","",gsub(" ","_",str_trim(names(ca))))
		tmp = data.frame(ca)
		defs = names(tmp)[str_detect(names(tmp),"^Defendant")]
		ptif = names(tmp)[str_detect(names(tmp),"^Plaintiff")]
		tmp$numPlaintiffs = sum(apply(tmp[defs],2,function(x) !is.na(x)))
		tmp$numDefendants = sum(apply(tmp[ptif],2,function(x) !is.na(x)))
		dt = rbind(dt,tmp,fill=TRUE)
	}
	dt[,c("Bank_search","from","to") := list(x$bank,x$dates_from,x$dates_to)]
	return(dt)

	# caution: check that Plaintiff_1 == bankname (there are also people suing banks!)
}


x = getData()
p = plots(x)
ta = tabs(x)


# remember current bank and add to a data.table

# analyse the data